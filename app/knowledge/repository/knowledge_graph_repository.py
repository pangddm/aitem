from __future__ import annotations

import re
from typing import Any

from app.knowledge.models import Incident
from app.memory.graph.schema import NodeType, RelationType


class KnowledgeGraphRepository:
    """
    Incident 知识图谱 Repository（GraphRAG）

    负责:
        Incident
           |
        Entity (Pod / Deployment / Namespace / Fault / ...)
           |
        因果链 (Fault -> CAUSES -> Fault)

    与 app/memory/repository/graph_repository.py 的区别:
        - GraphRepository 服务于 Memory（长期记忆）
        - KnowledgeGraphRepository 服务于 Incident（RAG 知识库）
    """

    def __init__(self, driver: Any):
        """
        Args:
            driver: neo4j.AsyncDriver 实例（不直接导入 neo4j 类型，
                    与 GraphRepository 保持一致，避免在未安装 neo4j
                    的环境中导入失败）
        """
        self.driver = driver
        self._indexes_created = False

    async def ensure_indexes(self) -> None:
        """
        创建 Neo4j 索引（幂等操作）

        优化点: 没有索引时图查询会全表扫描，数据量大时性能急剧下降
        """
        if self._indexes_created:
            return

        async with self.driver.session() as session:
            # Incident 节点索引
            await session.run(
                f"CREATE INDEX incident_id IF NOT EXISTS "
                f"FOR (i:{NodeType.INCIDENT.value}) ON (i.id)"
            )
            await session.run(
                f"CREATE INDEX incident_kb_id IF NOT EXISTS "
                f"FOR (i:{NodeType.INCIDENT.value}) ON (i.kb_id)"
            )

            # 实体节点索引（按 name 查询是核心操作）
            for label in [
                NodeType.ENTITY.value,
                NodeType.POD.value,
                NodeType.DEPLOYMENT.value,
                NodeType.NAMESPACE.value,
                NodeType.SERVICE.value,
                NodeType.NODE.value,
                NodeType.FAULT.value,
                NodeType.ERROR.value,
            ]:
                await session.run(
                    f"CREATE INDEX {label.lower()}_name IF NOT EXISTS "
                    f"FOR (n:{label}) ON (n.name)"
                )

        self._indexes_created = True
        print("[Neo4j] 索引创建完成")

    # ==========================================================
    # 入库时建图
    # ==========================================================

    async def insert_incident_graph(self, incident: Incident) -> None:
        """
        将一条 Incident 写入 Neo4j，并建立:
        1. Incident 节点
        2. Incident -> MENTIONS -> Entity (从 symptom/root_cause/solution/keywords 抽取)
        3. Fault -> CAUSES -> Fault (从 root_cause 识别因果)
        4. Incident -> DOCUMENTED_IN -> Document (可选)
        """
        async with self.driver.session() as session:
            # 1. 创建 Incident 节点
            await session.run(
                f"""
                MERGE (i:{NodeType.INCIDENT.value} {{id: $id}})
                SET i.title = $title,
                    i.summary = $summary,
                    i.symptom = $symptom,
                    i.root_cause = $root_cause,
                    i.solution = $solution,
                    i.category = $category,
                    i.kb_id = $kb_id,
                    i.owner = $owner,
                    i.created_at = $created_at
                """,
                id=incident.id,
                title=incident.title,
                summary=incident.summary,
                symptom=incident.symptom,
                root_cause=incident.root_cause,
                solution=incident.solution,
                category=incident.category.value,
                kb_id=incident.kb_id,
                owner=incident.owner,
                created_at=(
                    incident.created_at.isoformat()
                    if incident.created_at
                    else None
                ),
            )

            # 2. 关联 Document
            if incident.document_id:
                await session.run(
                    f"""
                    MERGE (d:Document {{id: $doc_id}})
                    MERGE (i:{NodeType.INCIDENT.value} {{id: $inc_id}})
                    MERGE (i)-[:{RelationType.DOCUMENTED_IN.value}]->(d)
                    """,
                    doc_id=incident.document_id,
                    inc_id=incident.id,
                )

            # 3. 抽取实体并建立 MENTIONS 关系
            entities = self._extract_entities_from_incident(incident)
            for entity in entities:
                entity_type, name = self._parse_entity(entity)
                label = entity_type
                await session.run(
                    f"""
                    MERGE (e:{label} {{name: $name}})
                    WITH e
                    MATCH (i:{NodeType.INCIDENT.value} {{id: $inc_id}})
                    MERGE (i)-[:{RelationType.MENTIONS.value}]->(e)
                    """,
                    name=name,
                    inc_id=incident.id,
                )

            # 4. 建立实体间结构关系 (Pod->Deployment->Namespace)
            await self._create_entity_relationships(session, entities)

            # 5. 识别 Fault 因果链
            await self._create_fault_causality(session, incident)

    async def batch_insert_incident_graph(
        self, incidents: list[Incident]
    ) -> None:
        """批量建图"""
        for incident in incidents:
            try:
                await self.insert_incident_graph(incident)
            except Exception as e:
                print(
                    f"[KnowledgeGraph] insert error for "
                    f"incident {incident.id}: {e}"
                )

    # ==========================================================
    # 检索时图扩展
    # ==========================================================

    async def search_related_incidents(
        self,
        kb_id: str,
        query: str,
        top_k: int = 10,
    ) -> list[tuple[str, float]]:
        """
        GraphRAG 检索: 从 query 抽取实体，沿图关系找关联 Incident

        策略:
        1. 从 query 提取实体关键词
        2. MATCH 实体节点 -> 找到 MENTIONS 这些实体的 Incident
        3. 沿 Fault->CAUSES->Fault 找因果链上的 Incident
        4. 按关联强度排序返回 [(incident_id, score), ...]

        返回: list of (incident_id, score)
        """
        keywords = self._extract_keywords(query)
        if not keywords:
            return []

        async with self.driver.session() as session:
            # 策略1: 实体直接关联
            result = await session.run(
                f"""
                MATCH (e)
                WHERE e.name IS NOT NULL
                  AND ANY(kw IN $keywords
                          WHERE toLower(e.name) CONTAINS toLower(kw))
                MATCH (i:{NodeType.INCIDENT.value})-[:{RelationType.MENTIONS.value}]->(e)
                WHERE i.kb_id = $kb_id
                RETURN DISTINCT i.id AS id,
                       count(DISTINCT e) AS entity_hits
                ORDER BY entity_hits DESC
                LIMIT $top_k
                """,
                keywords=keywords,
                kb_id=kb_id,
                top_k=top_k,
            )
            records = await result.fetch(top_k)

            results: dict[str, float] = {}
            for record in records:
                inc_id = record["id"]
                hits = int(record["entity_hits"])
                # 实体命中数越多分数越高
                results[inc_id] = results.get(inc_id, 0.0) + 0.3 * hits

            # 策略2: 因果链扩展 (找到的 Fault 的因果邻居 Incident)
            if results:
                known_ids = list(results.keys())
                result2 = await session.run(
                    f"""
                    MATCH (i1:{NodeType.INCIDENT.value})-[:{RelationType.MENTIONS.value}]->(f:{NodeType.FAULT.value})
                    WHERE i1.id IN $known_ids
                      AND i1.kb_id = $kb_id
                    MATCH (f)-[:{RelationType.CAUSES.value}*1..2]-(f2:{NodeType.FAULT.value})
                    MATCH (i2:{NodeType.INCIDENT.value})-[:{RelationType.MENTIONS.value}]->(f2)
                    WHERE i2.kb_id = $kb_id AND i2.id <> i1.id
                    RETURN DISTINCT i2.id AS id
                    LIMIT $top_k
                    """,
                    known_ids=known_ids,
                    kb_id=kb_id,
                    top_k=top_k,
                )
                records2 = await result2.fetch(top_k)
                for record in records2:
                    inc_id = record["id"]
                    # 因果链扩展的分数稍低
                    results[inc_id] = results.get(inc_id, 0.0) + 0.2

            # 归一化到 [0,1]
            if results:
                max_score = max(results.values())
                if max_score > 0:
                    results = {
                        k: v / max_score for k, v in results.items()
                    }

            return sorted(
                results.items(), key=lambda x: x[1], reverse=True
            )[:top_k]

    # ==========================================================
    # 删除
    # ==========================================================

    async def delete_incident_graph(self, incident_id: str) -> None:
        async with self.driver.session() as session:
            await session.run(
                f"""
                MATCH (i:{NodeType.INCIDENT.value} {{id: $id}})
                DETACH DELETE i
                """,
                id=incident_id,
            )

    # ==========================================================
    # Helpers
    # ==========================================================

    def _extract_entities_from_incident(
        self, incident: Incident
    ) -> list[str]:
        """
        从 Incident 的各字段抽取实体

        来源:
        1. keywords (最可靠)
        2. symptom / root_cause / solution (正则抽取 K8s 资源)
        """
        entities: list[str] = []

        # 1. keywords 直接作为实体
        for kw in incident.keywords:
            kw = kw.strip()
            if kw:
                entities.append(kw)

        # 2. 从文本字段抽取 K8s 资源名
        text_fields = [
            incident.symptom,
            incident.root_cause,
            incident.solution,
            incident.title,
        ]
        for text in text_fields:
            if not text:
                continue
            entities.extend(self._extract_k8s_entities(text))

        # 去重
        seen = set()
        unique = []
        for e in entities:
            e_lower = e.lower()
            if e_lower not in seen:
                seen.add(e_lower)
                unique.append(e)
        return unique

    @staticmethod
    def _extract_k8s_entities(text: str) -> list[str]:
        """从文本中抽取 K8s 资源实体"""
        entities = []

        # Pod: pod/xxx, po/xxx
        for m in re.finditer(
            r"\b(?:pod|po)\s*[\/\-]\s*([a-zA-Z0-9][a-zA-Z0-9\-_.]+)",
            text,
            re.IGNORECASE,
        ):
            entities.append(f"Pod/{m.group(1)}")

        # Deployment: deployment/xxx, deploy/xxx
        for m in re.finditer(
            r"\b(?:deployment|deploy)\s*[\/\-]\s*([a-zA-Z0-9][a-zA-Z0-9\-_.]+)",
            text,
            re.IGNORECASE,
        ):
            entities.append(f"Deployment/{m.group(1)}")

        # Namespace: namespace/xxx, ns/xxx
        for m in re.finditer(
            r"\b(?:namespace|ns)\s*[\/\-]\s*([a-zA-Z0-9][a-zA-Z0-9\-_.]+)",
            text,
            re.IGNORECASE,
        ):
            entities.append(f"Namespace/{m.group(1)}")

        # Service: service/xxx, svc/xxx
        for m in re.finditer(
            r"\b(?:service|svc)\s*[\/\-]\s*([a-zA-Z0-9][a-zA-Z0-9\-_.]+)",
            text,
            re.IGNORECASE,
        ):
            entities.append(f"Service/{m.group(1)}")

        # Node: node/xxx
        for m in re.finditer(
            r"\b(?:node)\s*[\/\-]\s*([a-zA-Z0-9][a-zA-Z0-9\-_.]+)",
            text,
            re.IGNORECASE,
        ):
            entities.append(f"Node/{m.group(1)}")

        # 常见故障名
        fault_patterns = [
            "CrashLoopBackOff",
            "ImagePullBackOff",
            "ErrImagePull",
            "OOMKilled",
            "Evicted",
            "Pending",
            "ContainerCreating",
            "Error",
            "Failed",
            "RestartCount",
        ]
        text_lower = text.lower()
        for fault in fault_patterns:
            if fault.lower() in text_lower:
                entities.append(f"Fault/{fault}")

        return entities

    def _parse_entity(self, entity: str) -> tuple[str, str]:
        """
        解析实体字符串 "Deployment/nginx" -> (NodeType, name)
        复用 GraphRepository 的解析逻辑
        """
        if "/" not in entity:
            # 纯关键词，归为 Entity
            return (NodeType.ENTITY.value, entity)

        prefix, name = entity.split("/", 1)
        mapping = {
            "Deployment": NodeType.DEPLOYMENT.value,
            "Pod": NodeType.POD.value,
            "Node": NodeType.NODE.value,
            "Namespace": NodeType.NAMESPACE.value,
            "Service": NodeType.SERVICE.value,
            "Fault": NodeType.FAULT.value,
            "Error": NodeType.ERROR.value,
        }
        return (mapping.get(prefix, NodeType.ENTITY.value), name)

    async def _create_entity_relationships(
        self, session, entities: list[str]
    ) -> None:
        """建立实体间结构关系: Pod->Deployment->Namespace"""
        parsed = [
            self._parse_entity(e)
            for e in entities
            if isinstance(e, str) and e.strip()
        ]
        if not parsed:
            return

        pod_nodes = [
            (t, n) for t, n in parsed if t == NodeType.POD.value
        ]
        deploy_nodes = [
            (t, n) for t, n in parsed if t == NodeType.DEPLOYMENT.value
        ]
        ns_nodes = [
            (t, n) for t, n in parsed if t == NodeType.NAMESPACE.value
        ]

        # Pod -> Deployment
        for _, pod_name in pod_nodes:
            for _, deploy_name in deploy_nodes:
                if self._pod_matches_deployment(pod_name, deploy_name):
                    await session.run(
                        f"""
                        MATCH (p:{NodeType.POD.value}{{name:$pod}}),
                              (d:{NodeType.DEPLOYMENT.value}{{name:$deploy}})
                        MERGE (p)-[:{RelationType.BELONGS_TO.value}]->(d)
                        """,
                        pod=pod_name,
                        deploy=deploy_name,
                    )

        # Pod -> Namespace
        for _, pod_name in pod_nodes:
            for _, ns_name in ns_nodes:
                await session.run(
                    f"""
                    MATCH (p:{NodeType.POD.value}{{name:$pod}}),
                          (n:{NodeType.NAMESPACE.value}{{name:$ns}})
                    MERGE (p)-[:{RelationType.BELONGS_TO.value}]->(n)
                    """,
                    pod=pod_name,
                    ns=ns_name,
                )

        # Deployment -> Namespace
        for _, deploy_name in deploy_nodes:
            for _, ns_name in ns_nodes:
                await session.run(
                    f"""
                    MATCH (d:{NodeType.DEPLOYMENT.value}{{name:$deploy}}),
                          (n:{NodeType.NAMESPACE.value}{{name:$ns}})
                    MERGE (d)-[:{RelationType.BELONGS_TO.value}]->(n)
                    """,
                    deploy=deploy_name,
                    ns=ns_name,
                )

    @staticmethod
    def _pod_matches_deployment(
        pod_name: str, deploy_name: str
    ) -> bool:
        if not pod_name or not deploy_name:
            return False
        p = pod_name.lower()
        d = deploy_name.lower()
        return p == d or p.startswith(d + "-") or p.startswith(d + "_")

    async def _create_fault_causality(
        self, session, incident: Incident
    ) -> None:
        """
        从 root_cause 文本识别因果链: Fault A -> CAUSES -> Fault B

        简单启发式:
        - 识别 "A 导致 B", "A 引起 B", "A caused B" 等模式
        """
        text = incident.root_cause or ""
        if not text:
            return

        # 因果关键词
        cause_patterns = [
            r"(.+?)\s*(?:导致|引起|造成|引发|使得|触发)\s*(.+?)",
            r"(.+?)\s*(?:caused?|leads?\s+to|results?\s+in|triggers?)\s*(.+?)",
        ]

        faults_in_text = self._extract_faults_from_text(text)
        if len(faults_in_text) < 2:
            return

        # 启发式: 前一个 fault 导致后一个 fault
        for i in range(len(faults_in_text) - 1):
            src = faults_in_text[i]
            dst = faults_in_text[i + 1]
            await session.run(
                f"""
                MERGE (f1:{NodeType.FAULT.value}{{name:$src}})
                MERGE (f2:{NodeType.FAULT.value}{{name:$dst}})
                MERGE (f1)-[:{RelationType.CAUSES.value}]->(f2)
                """,
                src=src,
                dst=dst,
            )

    @staticmethod
    def _extract_faults_from_text(text: str) -> list[str]:
        """从文本中抽取故障名"""
        faults = []
        fault_patterns = [
            "CrashLoopBackOff",
            "ImagePullBackOff",
            "ErrImagePull",
            "OOMKilled",
            "Evicted",
            "Pending",
            "ContainerCreating",
            "BackOff",
            "FailedScheduling",
            "FailedMount",
        ]
        text_lower = text.lower()
        for fault in fault_patterns:
            if fault.lower() in text_lower:
                faults.append(fault)
        return faults

    @staticmethod
    def _extract_keywords(query: str) -> list[str]:
        """从查询中提取关键词用于实体匹配"""
        if not query:
            return []
        stop_words = {
            "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
            "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
            "你", "会", "着", "没有", "看", "好", "自己", "这", "他", "她",
            "它", "们", "什么", "怎么", "如何", "为什么", "哪个", "哪些",
            "吗", "吧", "呢", "啊", "哦", "嗯",
            "the", "a", "an", "is", "are", "was", "were", "in", "on",
            "at", "to", "for", "of", "with", "by",
        }
        tokens = re.findall(
            r"[a-zA-Z0-9\u4e00-\u9fff]+", query.lower()
        )
        keywords = [
            t for t in tokens if t not in stop_words and len(t) >= 2
        ]
        return keywords[:8]