from __future__ import annotations


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