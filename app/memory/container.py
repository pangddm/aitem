from __future__ import annotations


from app.memory.extractor import (
    MemoryExtractor
)
from app.db.neo4j import neo4j

from app.memory.updater import (
    MemoryUpdater
)


from app.memory.memory_service import (
    MemoryService
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


from app.db.neo4j import (
    neo4j_driver
)



class MemoryContainer:



    def __init__(self):


        self._memory_service = None



    def create_service(

        self,

    ) -> MemoryService:


        if self._memory_service:


            return self._memory_service



        # =====================
        # Repository
        # =====================


        memory_repository = (

            MemoryRepository()

        )


        graph_repository = (

            GraphRepository(

                driver=neo4j.get_driver()

            )

        )



        # =====================
        # Retriever
        # =====================


        retriever = VectorRetriever()



        # =====================
        # Extractor
        # =====================


        extractor = MemoryExtractor()



        # =====================
        # Updater
        # =====================


        updater = MemoryUpdater(

            repository=memory_repository,

            retriever=retriever,

            graph_repository=graph_repository,

        )



        # =====================
        # Service
        # =====================


        self._memory_service = MemoryService(

            extractor=extractor,

            updater=updater,

        )



        return self._memory_service



memory_container = MemoryContainer()