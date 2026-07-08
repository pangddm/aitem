from __future__ import annotations

from abc import ABC
from abc import abstractmethod

import json
import asyncpg

from app.db.postgres import postgres
from app.llm.embedding.jina import embedding

from app.memory.classes import (
    Memory,
    MemoryType,
    MemorySource
)


class LongTermStore(ABC):

    @abstractmethod
    async def save(
        self,
        memory: Memory
    ):
        pass

    @abstractmethod
    async def update(
        self,
        memory: Memory
    ):
        pass

    @abstractmethod
    async def delete(
        self,
        memory_id: str
    ):
        pass

    @abstractmethod
    async def similarity_search(
        self,
        owner: str,
        query: str,
        top_k: int = 5
    ) -> list[Memory]:
        pass


class PGVectorStore(LongTermStore):

    def __init__(self):

        self.postgres = postgres

        self.embedding = embedding
    @staticmethod
    def _vector_to_pg(vector: list[float]) -> str:

        return "[" + ",".join(map(str, vector)) + "]"


    @staticmethod
    def _pg_to_vector(value):

        return value
    async def save(

        self,

        memory: Memory

    ):

        vector = await self.embedding.embed(
            memory.content
        )

        async with self.postgres.pool.acquire() as conn:

            await conn.execute(

                """
                INSERT INTO memory (

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

                VALUES (

                    $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12

                )
                """,

                memory.id,

                memory.owner,

                memory.type.value,

                memory.content,

                memory.summary,

                memory.source.value,

                memory.entities,

                memory.importance,

                json.dumps(memory.metadata),

                vector,

                memory.created_at,

                memory.updated_at

            )
    async def update(

        self,

        memory: Memory

    ):

        vector = await self.embedding.embed(
            memory.content
        )

        async with self.postgres.pool.acquire() as conn:

            await conn.execute(

                """
                UPDATE memory

                SET

                    type=$1,

                    content=$2,

                    summary=$3,

                    source=$4,

                    entities=$5,

                    importance=$6,

                    metadata=$7,

                    embedding=$8,

                    updated_at=$9

                WHERE id=$10
                """,

                memory.type.value,

                memory.content,

                memory.summary,

                memory.source.value,

                memory.entities,

                memory.importance,

                json.dumps(memory.metadata),

                vector,

                memory.updated_at,

                memory.id

            )
    async def delete(

        self,

        memory_id: str

    ):

        async with await self.postgres.acquire() as conn:

            await conn.execute(

                """
                DELETE FROM memory

                WHERE id=$1
                """,

                memory_id

            )


    async def get_by_id(

        self,

        memory_id: str

    ) -> Memory | None:

        async with await self.postgres.acquire() as conn:

            row = await conn.fetchrow(

                """
                SELECT *

                FROM memory

                WHERE id=$1
                """,

                memory_id

            )

        if row is None:

            return None

        return self._row_to_memory(row)


    async def list_by_owner(

        self,

        owner: str

    ) -> list[Memory]:

        async with await self.postgres.acquire() as conn:

            rows = await conn.fetch(

                """
                SELECT *

                FROM memory

                WHERE owner=$1

                ORDER BY created_at DESC
                """,

                owner

            )

        return [

            self._row_to_memory(row)

            for row in rows

        ]
    def _row_to_memory(

        self,

        row: asyncpg.Record

    ) -> Memory:

        metadata = row["metadata"]

        if isinstance(metadata, str):

            metadata = json.loads(metadata)

        elif metadata is None:

            metadata = {}

        return Memory(

            id=row["id"],

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

            metadata=metadata,

            created_at=row["created_at"],

            updated_at=row["updated_at"]

        )
    
    async def similarity_search(

        self,

        owner: str,

        query: str,

        top_k: int = 5

    ) -> list[Memory]:

        query_vector = await self.embedding.embed(
            query
        )

        query_vector = self._vector_to_pg(
            query_vector
        )

        async with await self.postgres.acquire() as conn:

            rows = await conn.fetch(

                """
                SELECT *

                FROM memory

                WHERE owner=$1

                ORDER BY embedding <=> $2::vector

                LIMIT $3
                """,

                owner,

                query_vector,

                top_k

            )

        return [

            self._row_to_memory(row)

            for row in rows

        ]
