"""图拓扑检索器：把 Neo4j 中沉淀的集群关系与操作审计，作为“参考提示”在查询时刻返回。

设计原则（方案A）：
- kubectl 实时指令是唯一事实源，本检索结果只是缓存提示。
- 返回文本带「须用 kubectl 复核」提示，AI 不得仅凭图断言事实。
"""
from __future__ import annotations

import re


class GraphTopologyRetriever:
    """从用户问题里识别资源，并返回相关拓扑 / 审计片段（空字符串表示无相关内容）"""

    def __init__(self, driver):
        self.driver = driver

    RESOURCE_KEYWORDS = {
        "deployment": "Deployment", "deploy": "Deployment",
        "statefulset": "StatefulSet", "sts": "StatefulSet",
        "daemonset": "DaemonSet", "ds": "DaemonSet",
        "job": "Job", "cronjob": "CronJob",
        "pod": "Pod", "pods": "Pod",
        "service": "Service", "svc": "Service",
        "endpoints": "Endpoints",
        "ingress": "Ingress",
        "configmap": "ConfigMap",
        "secret": "Secret",
        "rolebinding": "RoleBinding",
        "clusterrolebinding": "ClusterRoleBinding",
        "role": "Role", "clusterrole": "ClusterRole",
        "serviceaccount": "ServiceAccount", "sa": "ServiceAccount",
        "pvc": "PersistentVolumeClaim", "pv": "PersistentVolume",
        "namespace": "Namespace", "ns": "Namespace",
    }

    AUDIT_WORDS = ("最近", "历史", "审计", "做过", "操作", "变更", "什么时候", "谁")

    _STOPWORDS = ("nginx", "the", "and", "or", "for", "what", "how", "kubectl", "get", "give", "please", "now", "then", "into", "with")

    def _extract_names(self, query):
        names = []
        for tok in re.findall(r"[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?", (query or "").lower()):
            if len(tok) >= 2 and tok not in self.RESOURCE_KEYWORDS and tok not in self._STOPWORDS:
                names.append(tok)
        seen = set()
        out = []
        for n in names:
            if n not in seen:
                seen.add(n)
                out.append(n)
        return out[:6]

    async def recent_operations(self, owner, name=None, limit=8):
        if name:
            async with self.driver.session() as s:
                r = await s.run(
                    "MATCH (op:Operation {owner:$owner, entity_name:$name}) "
                    "RETURN op.action AS action, op.entity_type AS etype, op.entity_name AS name, op.at AS at "
                    "ORDER BY op.at DESC LIMIT $limit",
                    owner=owner, name=name, limit=limit,
                )
                return [dict(x) async for x in r]
        async with self.driver.session() as s:
            r = await s.run(
                "MATCH (op:Operation {owner:$owner}) "
                "RETURN op.action AS action, op.entity_type AS etype, op.entity_name AS name, op.at AS at "
                "ORDER BY op.at DESC LIMIT $limit",
                owner=owner, limit=limit,
            )
            return [dict(x) async for x in r]

    async def topology_path(self, owner, name):
        async with self.driver.session() as s:
            r = await s.run(
                "MATCH (u:User {id:$owner})-[:RELATED_TO]->(e) "
                "WHERE e.name = $name "
                "OPTIONAL MATCH (e)-[:BELONGS_TO]->(ns:Namespace) "
                "OPTIONAL MATCH (c)-[:BELONGS_TO]->(e) "
                "OPTIONAL MATCH (c)-[:BELONGS_TO]->(n2:Namespace) "
                "RETURN labels(e)[0] AS etype, e.name AS ename, "
                "       labels(c)[0] AS ctype, c.name AS cname, "
                "       labels(ns)[0] AS nst, ns.name AS nsname, "
                "       labels(n2)[0] AS n2t, n2.name AS n2name "
                "LIMIT 20",
                owner=owner, name=name,
            )
            return [dict(x) async for x in r]

    async def children(self, owner, name):
        async with self.driver.session() as s:
            r = await s.run(
                "MATCH (u:User {id:$owner})-[:RELATED_TO]->(e) "
                "WHERE e.name = $name "
                "MATCH (child)-[:BELONGS_TO]->(e) "
                "RETURN labels(child)[0] AS ctype, child.name AS cname "
                "ORDER BY cname LIMIT 40",
                owner=owner, name=name,
            )
            return [dict(x) async for x in r]

    async def rbac_chain(self, owner, name):
        async with self.driver.session() as s:
            r = await s.run(
                "MATCH (u:User {id:$owner})-[:RELATED_TO]->(b) "
                "WHERE (b:RoleBinding OR b:ClusterRoleBinding) AND b.name = $name "
                "OPTIONAL MATCH (b)-[:GRANTS]->(role) "
                "OPTIONAL MATCH (b)-[:ASSIGNED_TO]->(subj) "
                "RETURN labels(b)[0] AS bt, b.name AS bn, "
                "       labels(role)[0] AS rt, role.name AS rn, "
                "       labels(subj)[0] AS st, subj.name AS sn",
                owner=owner, name=name,
            )
            return [dict(x) async for x in r]

    async def retrieve_for_query(self, owner, query):
        q = (query or "").strip()
        if not q:
            return ""
        parts = []
        is_audit = any(w in q for w in self.AUDIT_WORDS)
        names = self._extract_names(q)

        if is_audit:
            ops = []
            for n in names[:3]:
                ops.extend(await self.recent_operations(owner, name=n, limit=5))
            if not ops:
                ops = await self.recent_operations(owner, limit=8)
            if ops:
                lines = []
                for o in ops[:8]:
                    et = o.get("etype") or "?"
                    an = o.get("name") or o.get("entity_name") or "?"
                    lines.append(f"- [{o.get('at','')}] {o.get('action','?')} {et}/{an}")
                parts.append("最近操作记录（历史，非当前状态）：\n" + "\n".join(lines))

        if not names and not is_audit:
            return parts and "\n\n".join(parts) or ""

        topo_lines = []
        for n in names:
            paths = await self.topology_path(owner, n)
            kids = await self.children(owner, n)
            chairs = [(p.get("ctype"), p.get("cname")) for p in paths if p.get("ctype")]
            ns_set = set()
            for p in paths:
                if p.get("nsname"):
                    ns_set.add(p.get("nsname"))
                if p.get("n2name"):
                    ns_set.add(p.get("n2name"))
            line_parts = []
            cts = [(p.get("etype"), p.get("ename")) for p in paths if p.get("etype")]
            if cts:
                line_parts.append(f"类型/名称: {cts[0][0]}/{cts[0][1]}")
            if ns_set:
                line_parts.append("命名空间: " + ", ".join(sorted(ns_set)))
            if chairs:
                line_parts.append("归属: " + ", ".join(f"{ct}/{cn}" for ct, cn in chairs if cn))
            if kids:
                line_parts.append("下属: " + ", ".join(f"{k['ctype']}/{k['cname']}" for k in kids[:10]))
            if line_parts:
                topo_lines.append(f"· {n}: " + "；".join(line_parts))
        if topo_lines:
            parts.append("图上记录的拓扑（缓存提示，须用 kubectl 复核）：\n" + "\n".join(topo_lines))

        rbac_lines = []
        for n in names:
            for c in await self.rbac_chain(owner, n):
                rbac_lines.append(
                    f"- {c.get('bt')}/{c.get('bn')} -GRANTS-> {c.get('rt')}/{c.get('rn')} "
                    + (f"；-ASSIGNED_TO-> {c.get('st')}/{c.get('sn')}" if c.get('sn') else "")
                )
        if rbac_lines:
            parts.append("RBAC 授权链条（缓存提示，须用 kubectl get rolebinding/clusterrolebinding -o wide 复核）：\n" + "\n".join(rbac_lines[:10]))

        return "\n\n".join(parts) if parts else ""
