from __future__ import annotations
from app.llm.embedding.factory import get_embedding

from app.memory.extractor import (
    MemoryExtractor
)

from app.memory.updater import (
    MemoryUpdater
)

from app.memory.classes import (
    MemorySource
)



class MemoryService:


    """
    Memory统一入口


    职责:

    1. 接收外部事件
    2. 调用Extractor
    3. 调用Updater


    不负责:

    - embedding
    - vector search
    - merge
    - database
    """



    def __init__(

        self,

        extractor: MemoryExtractor,

        updater: MemoryUpdater,

    ):
        self.embedding = get_embedding()

        self.extractor = extractor

        self.updater = updater



    async def process(

        self,

        owner: str,

        messages: list[dict],

        source: MemorySource = MemorySource.CHAT,

    ) -> dict:


        if not messages:


            return {

                "status": "skip",

                "reason": "empty messages",

            }



        try:


            # =========================
            # 1. Extract
            # =========================

            candidates = await (

                self.extractor.extract(

                    messages=messages,

                    source=source,

                )

            )


            if not candidates:


                return {

                    "status":"skip",

                    "reason":
                    "no memory candidate",

                }



            # =========================
            # 2. Update Memory
            # =========================

            result = await (

                self.updater.update(

                    owner=owner,

                    candidates=candidates,

                )

            )



            return {

                "status":"success",

                "count":len(candidates),

                "result":result,

            }



        except Exception as e:


            # Memory失败不能影响Agent主流程

            return {

                "status":"failed",

                "error":str(e),

            }
    async def search(

        self,

        owner: str,

        query: str,

    ):


        vector = await (

            self.embedding.embed(

                query

            )

        )


        memories = await (

            self.updater
            .retriever
            .retrieve(

                owner=owner,

                embedding=vector,

                top_k=5,

            )

        )


        return memories