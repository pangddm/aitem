from __future__ import annotations

from datetime import datetime

import asyncpg

from app.knowledge.models import KnowledgeBase


class KnowledgeBaseRepository:

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def create(
        self,
        kb: KnowledgeBase,
    ) -> None:

        async with self.pool.acquire() as conn:

            await conn.execute(
                """
                INSERT INTO knowledge_base(

                    id,
                    owner,
                    name,
                    description,
                    is_public,
                    created_at,
                    updated_at

                )

                VALUES(

                    $1,$2,$3,$4,$5,$6,$7
                )
                """,
                kb.id,
                kb.owner,
                kb.name,
                kb.description,
                kb.is_public,
                kb.created_at,
                kb.updated_at,
            )

    async def get(
        self,
        kb_id: str,
    ) -> KnowledgeBase | None:

        async with self.pool.acquire() as conn:

            row = await conn.fetchrow(
                """
                SELECT *

                FROM knowledge_base

                WHERE id=$1
                """,
                kb_id,
            )

        if row is None:
            return None

        return KnowledgeBase(

            id=str(row["id"]),

            owner=row["owner"],

            name=row["name"],

            description=row["description"],

            is_public=row["is_public"],

            created_at=row["created_at"],

            updated_at=row["updated_at"],
        )

    async def list_by_owner(
        self,
        owner: str,
    ) -> list[KnowledgeBase]:

        async with self.pool.acquire() as conn:

            rows = await conn.fetch(
                """
                SELECT *

                FROM knowledge_base

                WHERE owner=$1

                ORDER BY created_at DESC
                """,
                owner,
            )

        return [

            KnowledgeBase(

                id=str(row["id"]),

                owner=row["owner"],

                name=row["name"],

                description=row["description"],

                is_public=row["is_public"],

                created_at=row["created_at"],

                updated_at=row["updated_at"],

            )

            for row in rows

        ]

    async def update(
        self,
        kb: KnowledgeBase,
    ) -> None:

        async with self.pool.acquire() as conn:

            await conn.execute(
                """
                UPDATE knowledge_base SET
                    name=$2,
                    description=$3,
                    is_public=$4,
                    updated_at=$5
                WHERE id=$1
                """,
                kb.id,
                kb.name,
                kb.description,
                kb.is_public,
                kb.updated_at or datetime.utcnow(),
            )

    async def delete(
        self,
        kb_id: str,
    ) -> None:

        async with self.pool.acquire() as conn:

            await conn.execute(
                """
                DELETE FROM knowledge_base

                WHERE id=$1
                """,
                kb_id,
            )

    async def search_by_name(
        self,
        owner: str,
        query: str,
        top_k: int = 10,
    ) -> list[KnowledgeBase]:

        async with self.pool.acquire() as conn:

            rows = await conn.fetch(
                """
                SELECT *
                FROM knowledge_base
                WHERE owner=$1
                  AND name ILIKE $2
                ORDER BY created_at DESC
                LIMIT $3
                """,
                owner,
                f"%{query}%",
                top_k,
            )

        return [
            KnowledgeBase(
                id=str(row["id"]),
                owner=row["owner"],
                name=row["name"],
                description=row["description"],
                is_public=row["is_public"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    async def count_by_owner(
        self,
        owner: str,
    ) -> int:

        async with self.pool.acquire() as conn:

            total = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM knowledge_base
                WHERE owner=$1
                """,
                owner,
            )

            return total if total else 0