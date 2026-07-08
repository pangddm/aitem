from __future__ import annotations

from app.memory.entity.normalizer import EntityNormalizer
from app.memory.classes import (
    CandidateMemory
)


from app.memory.merge import (
    MemoryMerger
)


from app.memory.repository.memory_repository import (
    MemoryRepository
)


from app.memory.repository.graph_repository import (
    GraphRepository
)


from app.memory.repository.vector_retriever import (
    VectorRetriever
)


from app.llm.embedding.factory import (
    get_embedding
)



class MemoryUpdater:


    """
    Memory生命周期更新器


    负责:

    CandidateMemory

          |

    判断新增/更新/忽略

          |

    持久化


    """


    def __init__(

        self,

        repository: MemoryRepository,

        retriever: VectorRetriever,

        graph_repository: GraphRepository,

    ):

        self.entity_normalizer = EntityNormalizer()
        self.repository = repository

        self.retriever = retriever

        self.graph_repository = graph_repository


        self.embedding = get_embedding()


        self.merger = MemoryMerger()



    async def update(

        self,

        owner: str,

        candidates: list[CandidateMemory],

    ) -> dict:


        stats = {

            "insert":0,

            "update":0,

            "ignore":0,

        }



        for candidate in candidates:


            action = await (

                self._process_one(

                    owner,

                    candidate,

                )

            )


            stats[action] += 1



        return stats



    async def _process_one(

        self,

        owner: str,

        candidate: CandidateMemory,

    ) -> str:



        # =========================
        # 1. Embedding
        # =========================


        candidate.entities = (
            self.entity_normalizer
            .normalize(
                candidate.entities
            )
        )


        vector = await self.embedding.embed(
            candidate.content
        )



        # =========================
        # 2. Vector Retrieve
        # =========================


        memories = await (

            self.retriever.retrieve(

                owner=owner,

                embedding=vector,

                top_k=5,

            )

        )



        # =========================
        # 3. Merge Decision
        # =========================


        result = await (

            self.merger.merge(

                candidate,

                memories,

            )

        )



        # =========================
        # 4. Insert
        # =========================


        if result.action == "insert":



            memory = await (

                self.repository
                .insert_candidate(

                    owner=owner,

                    candidate=candidate,

                    embedding=vector,

                )

            )



            await (

                self.graph_repository
                .insert_memory_graph(

                    memory

                )

            )



            return "insert"



        # =========================
        # 5. Update
        # =========================


        if result.action == "update":


            if result.target is None:


                return "ignore"



            memory = await (

                self.repository
                .update_candidate(

                    memory_id=result.target.id,

                    candidate=candidate,

                    embedding=vector,

                )

            )



            await (

                self.graph_repository
                .update_memory_graph(

                    memory

                )

            )



            return "update"



        # =========================
        # 6. Ignore
        # =========================


        return "ignore"