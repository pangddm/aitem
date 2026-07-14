from __future__ import annotations


from app.memory.repository.memory_repository import (
    MemoryRepository
)



class VectorRetriever:



    """
    Memory向量检索器


    负责:

    根据embedding寻找历史相似Memory



    不负责:

    - 判断更新
    - merge

    """


    def __init__(

        self,

        threshold: float = 0.45,

    ):


        self.threshold = threshold


        self.repository = (
            MemoryRepository()
        )



    async def retrieve(

        self,

        owner: str,

        embedding: list[float],

        top_k: int = 5,

    ):



        memories = await (

            self.repository
            .search_similar(

                owner=owner,

                embedding=embedding,

                top_k=top_k,

            )

        )


        results = []


        print(
            "Retrieved memories:",
            [
                (
                    m.content,
                    m.similarity
                )
                for m in memories
            ]
        )
        for memory in memories:


            similarity = (

                getattr(

                    memory,

                    "similarity",

                    None

                )

            )


            if similarity is None:

                continue



            if similarity >= self.threshold:


                results.append(

                    memory

                )



        return results