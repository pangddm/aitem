from __future__ import annotations


from datetime import datetime

from uuid import uuid4


from app.db.postgres import postgres

from app.memory.classes import (
    Memory,
    MemoryType,
    MemorySource,
    CandidateMemory,
)



class MemoryRepository:



    """
    PostgreSQL Memory Repository


    对应:

    table memory


    """



    async def insert_candidate(

        self,

        owner: str,

        candidate: CandidateMemory,

        embedding: list[float],

    ) -> Memory:

        print("INSERT MEMORY:", candidate.content)

        memory_id = str(uuid4())


        now = datetime.now()



        async with postgres.pool.acquire() as conn:


            await conn.execute(

                """

                INSERT INTO memory

                (

                    id,

                    owner,

                    type,

                    content,

                    summary,

                    source,

                    entities,

                    importance,

                    metadata,

                    embedding,

                    created_at,

                    updated_at

                )


                VALUES

                (

                    $1,$2,$3,$4,$5,$6,

                    $7,$8,$9,$10,$11,$12

                )


                """,

                memory_id,

                owner,

                candidate.type.value,

                candidate.content,

                candidate.summary,

                candidate.source.value,

                candidate.entities,

                candidate.importance,

                candidate.metadata,

                embedding,

                now,

                now,

            )



        return Memory(

            id=memory_id,

            owner=owner,

            type=candidate.type,

            content=candidate.content,

            summary=candidate.summary,

            source=candidate.source,

            entities=candidate.entities,

            importance=candidate.importance,

            metadata=candidate.metadata,

            created_at=now,

            updated_at=now,

        )




    async def update_candidate(

        self,

        memory_id: str,

        candidate: CandidateMemory,

        embedding: list[float],

    ) -> Memory:



        now = datetime.now()



        async with postgres.pool.acquire() as conn:


            row = await conn.fetchrow(

                """

                UPDATE memory


                SET


                content=$2,

                summary=$3,

                type=$4,

                entities=$5,

                importance=$6,

                metadata=$7,

                embedding=$8,

                updated_at=$9



                WHERE id=$1



                RETURNING *


                """,

                memory_id,

                candidate.content,

                candidate.summary,

                candidate.type.value,

                candidate.entities,

                candidate.importance,

                candidate.metadata,

                embedding,

                now,

            )



        return self._to_memory(row)




    async def delete(

        self,

        memory_id: str,

    ):


        async with postgres.pool.acquire() as conn:


            await conn.execute(

                """

                DELETE FROM memory

                WHERE id=$1


                """,

                memory_id,

            )




    async def search_similar(

        self,

        owner: str,

        embedding: list[float],

        top_k: int = 5,

    ):
        print("owner:", owner)
        print("embedding type:", type(embedding))
        print("embedding length:", len(embedding))
        print("embedding first type:", type(embedding[0]))
        print("top_k:", top_k)

        async with postgres.pool.acquire() as conn:


            rows = await conn.fetch(

                """

                SELECT *,


                1 -

                (

                    embedding <=> $2

                )

                AS similarity



                FROM memory



                WHERE owner=$1



                ORDER BY

                embedding <=> $2



                LIMIT $3



                """,

                owner,

                embedding,

                top_k,

            )



        return [

            self._to_memory(row)

            for row in rows

        ]




    async def list_below_importance(

        self,

        threshold: float,

    ):


        async with postgres.pool.acquire() as conn:


            rows = await conn.fetch(

                """

                SELECT *

                FROM memory


                WHERE importance < $1


                """,

                threshold,

            )


        return [

            self._to_memory(row)

            for row in rows

        ]




    async def decay_by_type(

        self,

        memory_type: str,

        rate: float,

    ) -> int:



        async with postgres.pool.acquire() as conn:


            result = await conn.execute(

                """

                UPDATE memory


                SET


                importance = importance * $2,


                updated_at = NOW()



                WHERE type=$1



                """,

                memory_type,

                rate,

            )



        return int(
            result.split()[-1]
        )




    def _to_memory(

        self,

        row,

    ) -> Memory:


        return Memory(

            id=str(row["id"]),

            owner=row["owner"],

            type=MemoryType(
                row["type"]
            ),

            content=row["content"],

            summary=row["summary"],

            source=MemorySource(
                row["source"]
            ),

            entities=row["entities"] or [],

            importance=row["importance"],

            metadata=row["metadata"] or {},

            created_at=row["created_at"],

            updated_at=row["updated_at"],

            similarity=row.get("similarity"),

        )