"""结构化集群拓扑索引器。

从 Kubernetes API（kubectl get ... -o json）一次性拉取全量资源，
用对象元数据里的 ownerReferences / roleRef / subjects / endpoints.targetRef
确定地构建真实拓扑，以「清空重建」写入 Neo4j。

原则：
- kubectl（实际集群）是唯一真相源；
- 本模块是唯一写 K8s 拓扑节点/关系的地方（不再从 ad-hoc 命令输出猜拓扑）。
"""
from __future__ import annotations

import asyncio
import json


# 资源类型 → 查询
RESOURCE_QUERIES = {
    "Namespace": "kubectl get ns -o json",
    "Node": "kubectl get nodes -o json",
    "Deployment": "kubectl get deploy -A -o json",
    "StatefulSet": "kubectl get sts -A -o json",
    "DaemonSet": "kubectl get ds -A -o json",
    "Job": "kubectl get job -A -o json",
    "CronJob": "kubectl get cronjob -A -o json",
    "ReplicaSet": "kubectl get rs -A -o json",
    "Pod": "kubectl get pods -A -o json",
    "Service": "kubectl get svc -A -o json",
    "Endpoints": "kubectl get endpoints -A -o json",
    "Ingress": "kubectl get ingress -A -o json",
    "ConfigMap": "kubectl get cm -A -o json",
    "Secret": "kubectl get secret -A -o json",
    "PersistentVolume": "kubectl get pv -o json",
    "PersistentVolumeClaim": "kubectl get pvc -A -o json",
    "StorageClass": "kubectl get sc -o json",
    "ServiceAccount": "kubectl get sa -A -o json",
    "Role": "kubectl get role -A -o json",
    "ClusterRole": "kubectl get clusterrole -o json",
    "RoleBinding": "kubectl get rolebinding -A -o json",
    "ClusterRoleBinding": "kubectl get clusterrolebinding -o json",
}

CONTROLLER_KINDS = ("ReplicaSet", "StatefulSet", "DaemonSet", "Job", "CronJob")


def _items(doc: dict) -> list:
    return list((doc or {}).get("items", []) or [])


def _owner_refs(item: dict) -> list:
    return list((item.get("metadata", {}) or {}).get("ownerReferences", []) or [])


def _kind(item: dict) -> str:
    return item.get("kind") or ""


def _name(item: dict) -> str:
    return (item.get("metadata", {}) or {}).get("name", "")


def _ns(item: dict) -> str:
    return ((item.get("metadata", {}) or {}).get("namespace") or "")


def _first_owner(item: dict, kinds) -> tuple | None:
    for o in _owner_refs(item):
        if o.get("kind") in kinds:
            return (o.get("kind"), o.get("name"))
    return None


def add_node(nodes: dict, ntype: str, name: str, namespace: str = ""):
    if not name:
        return
    key = (ntype, name, namespace)
    nodes[key] = {"type": ntype, "name": name, "namespace": namespace}


def add_edge(edges: set, src, dst, rel):
    if src and dst:
        edges.add((src[0], src[1], src[2], dst[0], dst[1], dst[2], rel))


def key_of(ntype, name, namespace=""):
    return (ntype, name, namespace)


def build_snapshot(docs: dict) -> dict:
    """纯解析：docs = {资源类型: kubectl -o json 的结构化 dict}
    返回 {nodes: [...], edges: [...]}
    """
    nodes = {}
    edges = set()
    ns_set = set()

    # 命名空间
    for it in _items(docs.get("Namespace")):
        nm = _name(it)
        ns_set.add(nm)
        add_node(nodes, "Namespace", nm)

    # 控制器与对象（含归属 Namespace 的边）
    for kind in ("Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob",
                 "ReplicaSet", "Service", "Ingress", "ConfigMap", "Secret",
                 "PersistentVolumeClaim", "ServiceAccount", "Role", "RoleBinding",
                 "Endpoints"):
        for it in _items(docs.get(kind)):
            nm, nsn = _name(it), _ns(it)
            add_node(nodes, kind, nm, nsn)
            if nsn:
                ns_set.add(nsn)
                add_edge(edges, key_of(kind, nm, nsn), key_of("Namespace", nsn), "BELONGS_TO")

    # 集群级资源
    for kind in ("Node", "PersistentVolume", "StorageClass", "ClusterRole", "ClusterRoleBinding"):
        for it in _items(docs.get(kind)):
            add_node(nodes, kind, _name(it))

    # 命名空间节点（确保存在）
    for nsn in ns_set:
        add_node(nodes, "Namespace", nsn)

    # ReplicaSet -> Deployment（ownerReferences）
    for it in _items(docs.get("ReplicaSet")):
        nm, nsn = _name(it), _ns(it)
        own = _first_owner(it, ("Deployment",))
        if own:
            add_edge(edges, key_of("ReplicaSet", nm, nsn), key_of("Deployment", own[1], nsn), "BELONGS_TO")

    # Job -> CronJob（ownerReferences）
    for it in _items(docs.get("Job")):
        nm, nsn = _name(it), _ns(it)
        own = _first_owner(it, ("CronJob",))
        if own:
            add_edge(edges, key_of("Job", nm, nsn), key_of("CronJob", own[1], nsn), "BELONGS_TO")

    # Pod 节点；Pod -> 控制器（ownerReferences）; Pod -> Node（RUNS_ON）
    for it in _items(docs.get("Pod")):
        nm, nsn = _name(it), _ns(it)
        add_node(nodes, "Pod", nm, nsn)
        if nsn:
            ns_set.add(nsn)
        own = _first_owner(it, CONTROLLER_KINDS)
        if own:
            add_edge(edges, key_of("Pod", nm, nsn), key_of(own[0], own[1], nsn), "BELONGS_TO")
        node_name = (it.get("spec", {}) or {}).get("nodeName")
        if node_name:
            add_edge(edges, key_of("Pod", nm, nsn), key_of("Node", node_name), "RUNS_ON")

    # Endpoints -> Service（SELECTS，同名同命名空间）；Pod -> Endpoints（BACKS，经 targetRef）
    for it in _items(docs.get("Endpoints")):
        nm, nsn = _name(it), _ns(it)
        add_edge(edges, key_of("Endpoints", nm, nsn), key_of("Service", nm, nsn), "SELECTS")
        for sub in (it.get("subsets", []) or []):
            for addr in (sub.get("addresses", []) or []):
                tr = addr.get("targetRef")
                if tr and tr.get("kind") == "Pod" and tr.get("name"):
                    add_edge(edges, key_of("Pod", tr.get("name"), nsn), key_of("Endpoints", nm, nsn), "BACKS")

    # RBAC：binding -> GRANTS -> role/clusterrole；binding -> ASSIGNED_TO -> subject
    for kind, rolekind in (("RoleBinding", "Role"), ("ClusterRoleBinding", "ClusterRole")):
        for it in _items(docs.get(kind)):
            nm, nsn = _name(it), _ns(it)
            ref = it.get("roleRef", {}) or {}
            rk, rn = ref.get("kind"), ref.get("name")
            if rk and rn:
                add_edge(edges, key_of(kind, nm, nsn), key_of(rk, rn, nsn if rk == "Role" else ""), "GRANTS")
            for sub in (it.get("subjects", []) or []):
                st, sn = sub.get("kind"), sub.get("name")
                if not st or not sn:
                    continue
                if st == "ServiceAccount":
                    s_ns = sub.get("namespace") or nsn
                    add_node(nodes, "ServiceAccount", sn, s_ns)
                    add_edge(edges, key_of(kind, nm, nsn), key_of("ServiceAccount", sn, s_ns), "ASSIGNED_TO")
                elif st == "Group":
                    add_node(nodes, "Group", sn)
                    add_edge(edges, key_of(kind, nm, nsn), key_of("Group", sn), "ASSIGNED_TO")
                elif st == "User":
                    add_node(nodes, "ClusterUser", sn)
                    add_edge(edges, key_of(kind, nm, nsn), key_of("ClusterUser", sn), "ASSIGNED_TO")

    return {
        "nodes": [{"type": n[0], "name": n[1], "namespace": n[2]} for n in nodes.keys()],
        "edges": [{"src_type": e[0], "src": e[1], "src_ns": e[2],
                   "dst_type": e[3], "dst": e[4], "dst_ns": e[5], "rel": e[6]} for e in edges],
    }


DEFAULT_INTERVAL = 300
MIN_INTERVAL = 60
MAX_INTERVAL = 3600
_GLOBAL_KEY = "topology:interval_seconds"


def _interval_key(owner):
    if owner:
        return f"topology:interval_seconds:{owner}"
    return _GLOBAL_KEY


def get_topology_interval(owner=None) -> int:
    """读取某账号（或全局）的重建间隔（秒），未设置时用默认 300s"""
    try:
        from app.db.redis import redis_client
        v = redis_client.client.get(_interval_key(owner))
        if v:
            return max(MIN_INTERVAL, min(MAX_INTERVAL, int(v)))
    except Exception:
        pass
    return DEFAULT_INTERVAL


def set_topology_interval(seconds: int, owner=None) -> int:
    """保存某账号（或全局）的重建间隔（秒），限制在 [60, 3600]"""
    sec = max(MIN_INTERVAL, min(MAX_INTERVAL, int(seconds)))
    try:
        from app.db.redis import redis_client
        redis_client.client.set(_interval_key(owner), sec)
    except Exception as e:
        print(f"[TopologyIndexer] 保存间隔失败: {type(e).__name__}: {e}")
    return sec


class ClusterTopologyIndexer:
    """通过 SSH 执行结构化 kubectl 查询并重建 Neo4j 拓扑"""

    def __init__(self, driver):
        self.driver = driver

    @staticmethod
    async def _run(conn, command: str, host, port, username, password) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, conn, command,
                                          host, port, username, password)

    async def collect(self, conn, host, port, username, password) -> dict:
        docs = {}
        for kind, q in RESOURCE_QUERIES.items():
            try:
                raw = await self._run(conn, q, host, port, username, password)
                docs[kind] = json.loads(raw)
            except Exception as e:
                print(f"[TopologyIndexer] 查询 {kind} 失败: {type(e).__name__}: {e}")
                docs[kind] = {"items": []}
        return build_snapshot(docs)

    async def rebuild(self, owner, conn, host, port, username, password, repo) -> dict:
        snap = await self.collect(conn, host, port, username, password)
        stats = await repo.replace_topology(owner, snap["nodes"], snap["edges"])
        return {**stats, "nodes": len(snap["nodes"]), "edges": len(snap["edges"])}
