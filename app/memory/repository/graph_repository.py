from __future__ import annotations


import re
import uuid
from datetime import datetime


from app.memory.classes import Memory

from app.memory.graph.schema import (
    NodeType,
    RelationType,
)



class GraphRepository:


    """
    Neo4j Memory Graph Repository


    负责:

    Memory

       |

    Entity

       |

    Kubernetes Object



    """



    def __init__(

        self,

        driver,

    ):

        self.driver = driver



    async def insert_memory_graph(

        self,

        memory: Memory,

    ):


        async with self.driver.session() as session:
            print(f"[Neo4j 写入] memory={memory.id} type={memory.type.value} owner={memory.owner} importance={memory.importance}")
            print(f"[Neo4j 写入] content={memory.content[:150]}")
            print(f"[Neo4j 写入] entities={memory.entities}")
            _rels = self.build_entity_relationships(memory.entities)
            if _rels:
                print(f"[Neo4j 写入] entity_relations={_rels}")



            # ======================
            # 创建Memory节点
            # ======================


            await session.run(

                f"""

                MERGE (m:{NodeType.MEMORY.value}
                {{
                    id:$id
                }})


                SET

                    m.content=$content,

                    m.type=$type,

                    m.importance=$importance,

                    m.created_at=$created_at



                """,

                id=memory.id,

                content=memory.content,

                type=memory.type.value,

                importance=memory.importance,

                created_at=memory.created_at.isoformat(),

            )



            # ======================
            # User -> Memory
            # ======================


            await session.run(

                f"""

                MERGE (u:{NodeType.USER.value}
                {{
                    id:$owner
                }})



                MERGE

                (u)-[:{RelationType.HAS_MEMORY.value}]->(m)

                """,

                owner=memory.owner,

            )



            # ======================
            # Entity关系
            # ======================


            for entity in memory.entities:


                await self._create_entity_relation(

                    session,

                    memory.id,

                    entity,

                )

            await self._create_entity_relationships(

                session,

                memory.entities,

            )



    async def upsert_tool_entities(

        self,

        owner: str,

        command: str,

        tool_result: str,

        entities: list[str],
    ):

        if not entities:
            return

        async with self.driver.session() as session:
            print(f"[Neo4j 写入] tool_entities owner={owner} action={self._classify_action(command)} entities={entities}")

            await session.run(
                f"""
                MERGE (u:{NodeType.USER.value}{{id:$owner}})
                """,
                owner=owner,
            )

            action = self._classify_action(command)
            if action == "delete":
                # 删除资源：先记审计，再从图中移除，并级联删除其下属（删除 Deployment 时连其 ReplicaSet/Pod 一起删）
                for entity in entities:
                    entity_type, name = self._parse_entity(entity)
                    if entity_type in (NodeType.NAMESPACE.value, NodeType.USER.value):
                        continue
                    await self.record_operation(owner, entity_type, name, "delete", command, tool_result)
                    if entity_type == NodeType.DEPLOYMENT.value:
                        await session.run(
                            f"""
                            MATCH (d:{NodeType.DEPLOYMENT.value}{{name:$name}})
                            OPTIONAL MATCH (r:{NodeType.REPLICASET.value})-[:{RelationType.BELONGS_TO.value}]->(d)
                            OPTIONAL MATCH (p:{NodeType.POD.value})-[:{RelationType.BELONGS_TO.value}]->(r)
                            DETACH DELETE p, r, d
                            """,
                            name=name,
                        )
                    elif entity_type in (NodeType.STATEFULSET.value, NodeType.DAEMONSET.value, NodeType.JOB.value):
                        # 这些控制器直接管理 Pod（无 ReplicaSet）
                        await session.run(
                            f"""
                            MATCH (c:{entity_type}{{name:$name}})
                            OPTIONAL MATCH (p:{NodeType.POD.value})-[:{RelationType.BELONGS_TO.value}]->(c)
                            DETACH DELETE p, c
                            """,
                            name=name,
                        )
                    else:
                        await session.run(
                            f"""
                            MATCH (e:{entity_type}{{name:$name}})
                            DETACH DELETE e
                            """,
                            name=name,
                        )
                return


            for entity in entities:
                entity_type, name = self._parse_entity(entity)
                label = entity_type
                await session.run(
                    f"""
                    MERGE (e:{label}{{name:$name}})
                    SET e.last_seen_command=$command,
                        e.last_seen_result=$tool_result,
                        e.last_action=$action
                    MERGE (u:{NodeType.USER.value}{{id:$owner}})-[:{RelationType.RELATED_TO.value}]->(e)
                    """,
                    name=name,
                    command=command,
                    tool_result=tool_result,
                    owner=owner,
                    action=action,
                )

                if action:
                    await session.run(
                        f"""
                        MERGE (a:{NodeType.ENTITY.value}{{name:$action}})
                        MERGE (e)-[:{RelationType.OPERATED_ON.value}]->(a)
                        """,
                        action=action,
                    )

            await self._create_entity_relationships(session, entities)
            await self._record_state_change(session, action, entities, tool_result)
            # 审计：记录本次写操作
            for entity in entities:
                entity_type, name = self._parse_entity(entity)
                if entity_type in (NodeType.NAMESPACE.value, NodeType.USER.value):
                    continue
                await self.record_operation(owner, entity_type, name, action, command, tool_result)

    async def sync_pod_topology(

        self,

        owner: str,

        namespace: str,

        rows: list,

    ):

        """把 kubectl get pods 结果里的 Pod 归属拓扑写入图（支持 Deployment/StatefulSet/DaemonSet/Job）"""

        if not rows:

            return

        ctype_label = {

            "Deployment": NodeType.DEPLOYMENT.value,

            "StatefulSet": NodeType.STATEFULSET.value,

            "DaemonSet": NodeType.DAEMONSET.value,

            "Job": NodeType.JOB.value,

        }

        async with self.driver.session() as session:

            for row in rows:

                pod = (row or {}).get("pod")
                ctype = (row or {}).get("controller_type", "Deployment")
                cname = (row or {}).get("controller") or (row or {}).get("deployment")
                rs = (row or {}).get("replicaset")
                if not pod or not cname:
                    continue
                ns = namespace or "default"
                cLabel = ctype_label.get(ctype, NodeType.DEPLOYMENT.value)
                print(f"[Neo4j 写入] topology ns={ns} {ctype}/{cname}" + (f" -> ReplicaSet/{rs}" if rs else "") + f" -> Pod/{pod}")
                if rs:
                    await session.run(
                        f"""
                        MERGE (n:{NodeType.NAMESPACE.value}{{name:$ns}})
                        MERGE (c:{cLabel}{{name:$cname}})
                        MERGE (c)-[:{RelationType.BELONGS_TO.value}]->(n)
                        MERGE (r:{NodeType.REPLICASET.value}{{name:$rs}})
                        MERGE (r)-[:{RelationType.BELONGS_TO.value}]->(c)
                        MERGE (p:{NodeType.POD.value}{{name:$pod}})
                        MERGE (p)-[:{RelationType.BELONGS_TO.value}]->(r)
                        MERGE (u:{NodeType.USER.value}{{id:$owner}})-[:{RelationType.RELATED_TO.value}]->(c)
                        """,
                        ns=ns, cname=cname, rs=rs, pod=pod, owner=owner,
                    )
                else:
                    await session.run(
                        f"""
                        MERGE (n:{NodeType.NAMESPACE.value}{{name:$ns}})
                        MERGE (c:{cLabel}{{name:$cname}})
                        MERGE (c)-[:{RelationType.BELONGS_TO.value}]->(n)
                        MERGE (p:{NodeType.POD.value}{{name:$pod}})
                        MERGE (p)-[:{RelationType.BELONGS_TO.value}]->(c)
                        MERGE (u:{NodeType.USER.value}{{id:$owner}})-[:{RelationType.RELATED_TO.value}]->(c)
                        """,
                        ns=ns, cname=cname, pod=pod, owner=owner,
                    )


    async def sync_resource_list(self, owner, namespace, rows, cluster_scoped=False):
        """通用：把 get svc/ingress/configmap/secret/role/sa/pvc 等列表中的资源写入图（可选归属 Namespace）"""
        if not rows:
            return
        async with self.driver.session() as session:
            for row in rows:
                tlabel = (row or {}).get("type")
                name = (row or {}).get("name")
                if not tlabel or not name:
                    continue
                if cluster_scoped:
                    await session.run(
                        f"""
                        MERGE (e:{tlabel}{{name:$name}})
                        MERGE (u:{NodeType.USER.value}{{id:$owner}})-[:{RelationType.RELATED_TO.value}]->(e)
                        """,
                        name=name, owner=owner,
                    )
                else:
                    await session.run(
                        f"""
                        MERGE (n:{NodeType.NAMESPACE.value}{{name:$ns}})
                        MERGE (e:{tlabel}{{name:$name}})
                        MERGE (e)-[:{RelationType.BELONGS_TO.value}]->(n)
                        MERGE (u:{NodeType.USER.value}{{id:$owner}})-[:{RelationType.RELATED_TO.value}]->(e)
                        """,
                        ns=namespace or "default", name=name, owner=owner,
                    )

    async def sync_endpoints(self, owner, namespace, rows):
        """把 get endpoints 结果落图：Endpoints 归属 Namespace，并与同名 Service 建立 SELECTS 关系"""
        if not rows:
            return
        async with self.driver.session() as session:
            for row in rows:
                name = (row or {}).get("service")
                if not name:
                    continue
                ns = namespace or "default"
                await session.run(
                    f"""
                    MERGE (n:{NodeType.NAMESPACE.value}{{name:$ns}})
                    MERGE (ep:{NodeType.ENDPOINTS.value}{{name:$name}})
                    MERGE (ep)-[:{RelationType.BELONGS_TO.value}]->(n)
                    MERGE (u:{NodeType.USER.value}{{id:$owner}})-[:{RelationType.RELATED_TO.value}]->(ep)
                    OPTIONAL MATCH (svc:{NodeType.SERVICE.value}{{name:$name}})
                    FOREACH (__s IN CASE WHEN svc IS NOT NULL THEN [1] ELSE [] END |
                        MERGE (ep)-[:{RelationType.SELECTS.value}]->(svc))
                    """,
                    ns=ns, name=name, owner=owner,
                )

    async def sync_rbac(self, owner, rows):
        """把 RoleBinding / ClusterRoleBinding 落图：Binding -> GRANTS -> Role/ClusterRole；Binding -> ASSIGNED_TO -> Subject"""
        if not rows:
            return
        async with self.driver.session() as session:
            for rb in rows:
                kind = (rb or {}).get("kind")
                name = (rb or {}).get("name")
                ns = (rb or {}).get("namespace") or "default"
                role = (rb or {}).get("role")
                role_kind = (rb or {}).get("role_kind") or "ClusterRole"
                if not name:
                    continue
                is_cluster = kind != "RoleBinding"
                binding_label = NodeType.CLUSTERROLEBINDING.value if is_cluster else NodeType.ROLEBINDING.value
                role_label = NodeType.CLUSTERROLE.value if role_kind == "ClusterRole" else NodeType.ROLE.value
                if is_cluster:
                    await session.run(
                        f"""
                        MERGE (b:{binding_label}{{name:$name}})
                        MERGE (u:{NodeType.USER.value}{{id:$owner}})-[:{RelationType.RELATED_TO.value}]->(b)
                        """,
                        name=name, owner=owner,
                    )
                else:
                    await session.run(
                        f"""
                        MERGE (n:{NodeType.NAMESPACE.value}{{name:$ns}})
                        MERGE (b:{binding_label}{{name:$name}})
                        MERGE (b)-[:{RelationType.BELONGS_TO.value}]->(n)
                        MERGE (u:{NodeType.USER.value}{{id:$owner}})-[:{RelationType.RELATED_TO.value}]->(b)
                        """,
                        ns=ns, name=name, owner=owner,
                    )
                if role:
                    await session.run(
                        f"""
                        MATCH (b:{binding_label}{{name:$name}})
                        MERGE (r:{role_label}{{name:$role}})
                        MERGE (b)-[:{RelationType.GRANTS.value}]->(r)
                        """,
                        name=name, role=role,
                    )
                for subj in (rb or {}).get("subjects", []) or []:
                    stype = subj.get("type")
                    sname = subj.get("name")
                    sns = subj.get("namespace")
                    if not sname:
                        continue
                    if stype == "ServiceAccount":
                        subject_label = NodeType.SERVICEACCOUNT.value
                        if sns:
                            await session.run(
                                f"""
                                MATCH (b:{binding_label}{{name:$bindname}})
                                MERGE (n:{NodeType.NAMESPACE.value}{{name:$ns}})
                                MERGE (sa:{subject_label}{{name:$sname}})
                                MERGE (sa)-[:{RelationType.BELONGS_TO.value}]->(n)
                                MERGE (b)-[:{RelationType.ASSIGNED_TO.value}]->(sa)
                                """,
                                bindname=name, ns=sns, sname=sname,
                            )
                        else:
                            await session.run(
                                f"""
                                MATCH (b:{binding_label}{{name:$bindname}})
                                MERGE (sa:{subject_label}{{name:$sname}})
                                MERGE (b)-[:{RelationType.ASSIGNED_TO.value}]->(sa)
                                """,
                                bindname=name, sname=sname,
                            )
                    elif stype == "Group":
                        subject_label = NodeType.GROUP.value
                        await session.run(
                            f"""
                            MATCH (b:{binding_label}{{name:$bindname}})
                            MERGE (g:{subject_label}{{name:$sname}})
                            MERGE (b)-[:{RelationType.ASSIGNED_TO.value}]->(g)
                            """,
                            bindname=name, sname=sname,
                        )
                    elif stype == "User":
                        subject_label = NodeType.CLUSTERUSER.value
                        await session.run(
                            f"""
                            MATCH (b:{binding_label}{{name:$bindname}})
                            MERGE (cu:{subject_label}{{name:$sname}})
                            MERGE (b)-[:{RelationType.ASSIGNED_TO.value}]->(cu)
                            """,
                            bindname=name, sname=sname,
                        )

    async def record_operation(self, owner, entity_type, entity_name, action, command, result):
        """追加一条不可变操作审计事件（append-only 历史，供查询时核对“最近对资源做过什么”）"""
        opid = uuid.uuid4().hex
        at = datetime.utcnow().isoformat()
        try:
            async with self.driver.session() as session:
                await session.run(
                    f"""
                    CREATE (op:{NodeType.OPERATION.value} {{
                        id:$opid, owner:$owner, entity_type:$entity_type,
                        entity_name:$entity_name, action:$action,
                        command:$command, result:$result, at:$at
                    }})
                    MERGE (u:{NodeType.USER.value}{{id:$owner}})-[:{RelationType.PERFORMED.value}]->(op)
                    """,
                    opid=opid, owner=owner, entity_type=entity_type,
                    entity_name=entity_name, action=action,
                    command=(command or "")[:200], result=(result or "")[:200], at=at,
                )
                # 若实体仍在图上，把 Operation 挂到实体上（已删除的实体只保留 Operation 字符串字段）
                await session.run(
                    f"""
                    MATCH (e:Entity) WHERE e.name = $name
                    WITH e LIMIT 1
                    MATCH (op:{NodeType.OPERATION.value}{{id:$opid}})
                    MERGE (e)-[:{RelationType.OPERATED_ON.value}]->(op)
                    """,
                    name=entity_name, opid=opid,
                )
        except Exception as e:
            print(f"[Neo4j 审计] record_operation 失败: {type(e).__name__}: {e}")

    K8S_LABELS = (
        "Namespace", "Node", "Pod", "Deployment", "ReplicaSet", "StatefulSet",
        "DaemonSet", "Job", "CronJob", "Service", "Endpoints", "Ingress",
        "ConfigMap", "Secret", "Role", "ClusterRole", "RoleBinding",
        "ClusterRoleBinding", "ServiceAccount", "Group", "ClusterUser",
        "PersistentVolumeClaim", "PersistentVolume", "StorageClass",
    )
    K8S_RELS = (
        "BELONGS_TO", "GRANTS", "ASSIGNED_TO", "SELECTS", "BACKS",
        "RUNS_ON", "EXPOSES", "USES", "DEPENDS_ON", "RUNS_IN",
    )

    # 属于“用户命名空间对象”、可安全随重建删除的标签（共享集群级节点保留：Namespace/Node/PV/StorageClass/ClusterRole/CRB/Group/ClusterUser）
    OWNED_LABELS = tuple(
        l for l in K8S_LABELS
        if l not in ("Namespace", "Node", "PersistentVolume", "StorageClass",
                     "ClusterRole", "ClusterRoleBinding", "Group", "ClusterUser")
    )

    async def replace_topology(self, owner, nodes, edges):
        """以「清空重建」写入某账号的 K8s 拓扑。

        每个账号的节点都带 owner 属性，实现账号间隔离（不同账号连不同集群互不串扰）。
        只删除本账号拥有的命名空间级对象，不动共享的 Namespace/Node/ClusterRole 等集群级节点，
        避免误删其它账号/共享拓扑。
        """
        if not nodes:
            return {"created_nodes": 0, "created_edges": 0}
        # 清空该账号的 K8s 拓扑：删除本账号拥有的全部 K8s 节点（带 owner），
        # 以及与本账号关联但尚未打 owner 的历史节点（迁移）。只影响本账号，不碰其它账号。
        k8s_sql = " OR ".join(f"e:{lbl}" for lbl in self.K8S_LABELS)
        cleared = 0
        async with self.driver.session() as session:
            r = await session.run(
                f"""
                MATCH (u:{NodeType.USER.value}{{id:$owner}})-[:{RelationType.RELATED_TO.value}]->(e)
                WHERE {k8s_sql} AND (e.owner = $owner OR e.owner IS NULL)
                DETACH DELETE e
                RETURN count(e) AS c
                """,
                owner=owner,
            )
            row = await r.single()
            cleared = row["c"] if row else 0

            # 2) 写入节点（带 owner 隔离）+ Namespace 归属 + 用户关联
            for nd in nodes:
                label = nd["type"]
                name = nd["name"]
                nsp = nd.get("namespace") or ""
                if nsp:
                    await session.run(
                        f"""
                        MERGE (n:{NodeType.NAMESPACE.value}{{name:$ns, owner:$owner}})
                        MERGE (e:{label}{{name:$name, namespace:$ns, owner:$owner}})
                        MERGE (e)-[:{RelationType.BELONGS_TO.value}]->(n)
                        MERGE (u:{NodeType.USER.value}{{id:$owner}})-[:{RelationType.RELATED_TO.value}]->(e)
                        """,
                        ns=nsp, name=name, owner=owner,
                    )
                else:
                    await session.run(
                        f"""
                        MERGE (e:{label}{{name:$name, owner:$owner}})
                        MERGE (u:{NodeType.USER.value}{{id:$owner}})-[:{RelationType.RELATED_TO.value}]->(e)
                        """,
                        name=name, owner=owner,
                    )

            # 3) 写入关系（Namespace 归属边已在第2步建立，跳过；均按 owner 匹配隔离）
            for e in edges:
                if e["dst_type"] == "Namespace" and e["rel"] == "BELONGS_TO":
                    continue
                src_ns = e.get("src_ns") or ""
                dst_ns = e.get("dst_ns") or ""
                src_mat = (f"{{name:$sn, namespace:$sns, owner:$owner}}" if src_ns else f"{{name:$sn, owner:$owner}}")
                dst_mat = (f"{{name:$dn, namespace:$dns, owner:$owner}}" if dst_ns else f"{{name:$dn, owner:$owner}}")
                await session.run(
                    f"""
                    MATCH (a:{e['src_type']}{src_mat})
                    MATCH (b:{e['dst_type']}{dst_mat})
                    MERGE (a)-[:{e['rel']}]->(b)
                    """,
                    sn=e["src"], sns=src_ns,
                    dn=e["dst"], dns=dst_ns,
                    owner=owner,
                )
        return {"cleared": cleared, "created_edges": len(edges)}

    def _classify_action(self, command: str) -> str:
        lower = command.lower()
        if "scale" in lower:
            return "scale"
        if "delete" in lower:
            return "delete"
        if "create" in lower or "apply" in lower:
            return "create"
        if "describe" in lower or "get" in lower:
            return "inspect"
        return "operate"

    async def _record_state_change(self, session, action: str, entities: list[str], tool_result: str):
        if not action or not entities:
            return

        state = self._summarize_state(tool_result)
        if not state:
            return

        for entity in entities:
            entity_type, name = self._parse_entity(entity)
            label = entity_type
            await session.run(
                f"""
                MERGE (e:{label}{{name:$name}})
                SET e.last_state=$state,
                    e.last_state_changed_at=timestamp()
                """,
                name=name,
                state=state,
            )

    def _summarize_state(self, tool_result: str) -> str | None:
        if not tool_result:
            return None
        text = tool_result.strip()
        if len(text) > 160:
            text = text[:160]
        return text

    async def _create_entity_relation(

        self,

        session,

        memory_id: str,

        entity: str,

    ):


        entity_type, name = (
            self._parse_entity(entity)
        )


        label = entity_type



        await session.run(

            f"""

            MERGE (e:{label}
            {{
                name:$name
            }})



            WITH e


            MATCH

            (m:Memory
            {{
                id:$memory_id
            }})


            MERGE

            (m)-[:{RelationType.MENTIONS.value}]->(e)


            """,

            name=name,

            memory_id=memory_id,

        )



    def build_entity_relationships(

        self,

        entities: list[str],

    ) -> list[tuple[str, str, str, str, str]]:

        parsed = [
            self._parse_entity(entity)
            for entity in entities
            if isinstance(entity, str) and entity.strip()
        ]

        if not parsed:
            return []

        pod_nodes = [
            (entity_type, name)
            for entity_type, name in parsed
            if entity_type == NodeType.POD.value
        ]

        deployment_nodes = [
            (entity_type, name)
            for entity_type, name in parsed
            if entity_type == NodeType.DEPLOYMENT.value
        ]

        namespace_nodes = [
            (entity_type, name)
            for entity_type, name in parsed
            if entity_type == NodeType.NAMESPACE.value
        ]

        relations: list[tuple[str, str, str, str, str]] = []

        for _, pod_name in pod_nodes:
            for _, deployment_name in deployment_nodes:
                if self._pod_matches_deployment(pod_name, deployment_name):
                    relations.append((NodeType.POD.value, pod_name, NodeType.DEPLOYMENT.value, deployment_name, RelationType.BELONGS_TO.value))

            for _, namespace_name in namespace_nodes:
                relations.append((NodeType.POD.value, pod_name, NodeType.NAMESPACE.value, namespace_name, RelationType.BELONGS_TO.value))

        for _, deployment_name in deployment_nodes:
            for _, namespace_name in namespace_nodes:
                relations.append((NodeType.DEPLOYMENT.value, deployment_name, NodeType.NAMESPACE.value, namespace_name, RelationType.BELONGS_TO.value))

        for index, (_, pod_a) in enumerate(pod_nodes):
            for _, pod_b in pod_nodes[index + 1:]:
                if self._pod_family_matches(pod_a, pod_b):
                    relations.append((NodeType.POD.value, pod_a, NodeType.POD.value, pod_b, RelationType.RELATED_TO.value))

        return relations

    def _pod_matches_deployment(self, pod_name: str, deployment_name: str) -> bool:
        if not pod_name or not deployment_name:
            return False
        pod_name = pod_name.lower()
        deployment_name = deployment_name.lower()
        return (
            pod_name == deployment_name
            or pod_name.startswith(deployment_name + "-")
            or pod_name.startswith(deployment_name + "_")
            or deployment_name in pod_name
        )

    def _pod_family_matches(self, pod_a: str, pod_b: str) -> bool:
        if not pod_a or not pod_b:
            return False
        prefix_a = re.split(r"[-_]", pod_a.lower(), maxsplit=1)[0]
        prefix_b = re.split(r"[-_]", pod_b.lower(), maxsplit=1)[0]
        return bool(prefix_a and prefix_a == prefix_b)

    async def _create_entity_relationships(

        self,

        session,

        entities: list[str],

    ):

        for source_type, source_name, target_type, target_name, relation_type in self.build_entity_relationships(entities):
            await session.run(

                f"""

                MATCH
                    (src:{source_type}{{name:$source_name}}),
                    (dst:{target_type}{{name:$target_name}})

                MERGE (src)-[:{relation_type}]->(dst)

                """,

                source_name=source_name,
                target_name=target_name,
            )

    def _parse_entity(

        self,

        entity: str,

    ):


        """
        entity格式:

        Deployment/nginx

        Pod/nginx-xxx

        Fault/CrashLoopBackOff


        """



        if "/" not in entity:


            return (

                NodeType.ENTITY.value,

                entity

            )



        prefix, name = entity.split(

            "/",

            1

        )



        mapping = {


            "Deployment":
            NodeType.DEPLOYMENT.value,

            "Deploy":
            NodeType.DEPLOYMENT.value,


            "Pod":
            NodeType.POD.value,


            "Node":
            NodeType.NODE.value,


            "Namespace":
            NodeType.NAMESPACE.value,


            "Service":
            NodeType.SERVICE.value,

            "Svc":
            NodeType.SERVICE.value,


            "StatefulSet":
            NodeType.STATEFULSET.value,


            "DaemonSet":
            NodeType.DAEMONSET.value,


            "Job":
            NodeType.JOB.value,


            "CronJob":
            NodeType.CRONJOB.value,


            "Endpoints":
            NodeType.ENDPOINTS.value,


            "Ingress":
            NodeType.INGRESS.value,


            "ConfigMap":
            NodeType.CONFIGMAP.value,


            "Secret":
            NodeType.SECRET.value,


            "Role":
            NodeType.ROLE.value,


            "ClusterRole":
            NodeType.CLUSTERROLE.value,


            "RoleBinding":
            NodeType.ROLEBINDING.value,


            "ClusterRoleBinding":
            NodeType.CLUSTERROLEBINDING.value,


            "ServiceAccount":
            NodeType.SERVICEACCOUNT.value,


            "Group":
            NodeType.GROUP.value,


            "User":
            NodeType.CLUSTERUSER.value,


            "PersistentVolumeClaim":
            NodeType.PVC.value,


            "PersistentVolume":
            NodeType.PV.value,


            "StorageClass":
            NodeType.STORAGECLASS.value,


            "Fault":
            NodeType.FAULT.value,


            "Error":
            NodeType.ERROR.value,

        }



        return (

            mapping.get(

                prefix,

                NodeType.ENTITY.value

            ),

            name

        )



    async def update_memory_graph(

        self,

        memory: Memory,

    ):


        async with self.driver.session() as session:
            print(f"[Neo4j 写入] update memory={memory.id} type={memory.type.value} content={memory.content[:150]}")



            await session.run(

                """

                MATCH

                (m:Memory{id:$id})


                SET

                m.content=$content,

                m.importance=$importance,

                m.updated_at=$updated_at


                """,

                id=memory.id,

                content=memory.content,

                importance=memory.importance,

                updated_at=datetime.utcnow().isoformat(),

            )



    async def mark_memory_superseded(

        self,

        memory_id: str,

        superseded_by: str,
    ):

        async with self.driver.session() as session:

            await session.run(

                """

                MATCH (m:Memory{id:$id})

                SET m.superseded=$superseded,
                    m.superseded_by=$superseded_by

                """,

                id=memory_id,
                superseded=True,
                superseded_by=superseded_by,
            )


    async def link_memory_replacement(

        self,

        old_memory_id: str,

        new_memory_id: str,
        reason: str,
        version: int,
        replaced_at: str,
        owner: str,
    ):

        async with self.driver.session() as session:

            await session.run(

                f"""

                MATCH
                    (old:Memory{{id:$old_memory_id}}),
                    (new:Memory{{id:$new_memory_id}}),
                    (u:User{{id:$owner}})

                MERGE (old)-[:{RelationType.SUPERSEDED_BY.value}{{reason:$reason, version:$version, replaced_at:$replaced_at}}]->(new)
                MERGE (new)-[:{RelationType.REPLACED_BY.value}{{reason:$reason, version:$version, replaced_at:$replaced_at}}]->(old)
                MERGE (u)-[:{RelationType.HAS_MEMORY.value}]->(new)

                MERGE (r:{NodeType.REASON.value}{{name:$reason}})
                MERGE (u)-[:REPORTED_REASON]->(r)
                MERGE (r)-[:CAUSES_REPLACEMENT]->(new)

                """,

                old_memory_id=old_memory_id,
                new_memory_id=new_memory_id,
                reason=reason,
                version=version,
                replaced_at=replaced_at,
                owner=owner,
            )


    async def delete_memory_graph(

        self,

        memory_id: str,

    ):


        async with self.driver.session() as session:


            await session.run(

                """

                MATCH

                (m:Memory{id:$id})


                DETACH DELETE m


                """,

                id=memory_id,

            )
