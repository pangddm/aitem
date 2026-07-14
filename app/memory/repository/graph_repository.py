from __future__ import annotations


import re
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
            await session.run(
                f"""
                MERGE (u:{NodeType.USER.value}{{id:$owner}})
                """,
                owner=owner,
            )

            action = self._classify_action(command)
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


            "Pod":
            NodeType.POD.value,


            "Node":
            NodeType.NODE.value,


            "Namespace":
            NodeType.NAMESPACE.value,


            "Service":
            NodeType.SERVICE.value,


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