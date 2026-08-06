from __future__ import annotations

from datetime import datetime
from uuid import UUID

import asyncpg

from app.knowledge.models import KnowledgeBase


def _valid_uuid(value: str) -> UUID | None:
    """安全地将字符串转为 UUID，无效则返回 None"""
    try:
        return UUID(value)
    except (ValueError, AttributeError, TypeError):
        return None


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
                _valid_uuid(kb.owner) or UUID(int=0),
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
        owner_uuid = _valid_uuid(owner)
        if owner_uuid is None:
            return []

        async with self.pool.acquire() as conn:

            rows = await conn.fetch(
                """
                SELECT *

                FROM knowledge_base

                WHERE owner=$1

                ORDER BY created_at DESC
                """,
                owner_uuid,
            )

        return [self._to_kb(row) for row in rows]

    async def list_accessible(
        self,
        owner: str,
    ) -> list[KnowledgeBase]:
        """
        返回用户可访问的所有知识库（自己拥有的 + 公开的）

        用于知识库检索时，让用户能搜索到公开知识库中的内容。
        """
        owner_uuid = _valid_uuid(owner)
        if owner_uuid is None:
            # 无效 UUID，只返回公开知识库
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT *
                    FROM knowledge_base
                    WHERE is_public=TRUE
                    ORDER BY created_at DESC
                    """
                )
            return [self._to_kb(row) for row in rows]

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM knowledge_base
                WHERE owner=$1 OR is_public=TRUE
                ORDER BY
                    CASE WHEN owner=$1 THEN 0 ELSE 1 END,
                    created_at DESC
                """,
                owner_uuid,
            )

        return [self._to_kb(row) for row in rows]

    async def list_public(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[KnowledgeBase], int]:
        """列出所有公开知识库（分页）"""
        offset = (page - 1) * page_size
        async with self.pool.acquire() as conn:
            total = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM knowledge_base
                WHERE is_public=TRUE
                """
            )
            rows = await conn.fetch(
                """
                SELECT *
                FROM knowledge_base
                WHERE is_public=TRUE
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                page_size,
                offset,
            )

        return [self._to_kb(row) for row in rows], (total or 0)

    async def is_accessible(
        self,
        kb_id: str,
        owner: str,
    ) -> bool:
        """检查用户是否有权访问某个知识库（拥有或公开）"""
        owner_uuid = _valid_uuid(owner)
        if owner_uuid is None:
            return False

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 1
                FROM knowledge_base
                WHERE id=$1 AND (owner=$2 OR is_public=TRUE)
                """,
                kb_id,
                owner_uuid,
            )
        return row is not None

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
        """搜索知识库（包含自己的 + 公开的）"""
        owner_uuid = _valid_uuid(owner)
        if owner_uuid is None:
            return []

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM knowledge_base
                WHERE (owner=$1 OR is_public=TRUE)
                  AND name ILIKE $2
                ORDER BY created_at DESC
                LIMIT $3
                """,
                owner_uuid,
                f"%{query}%",
                top_k,
            )

        return [self._to_kb(row) for row in rows]

    async def count_by_owner(
        self,
        owner: str,
    ) -> int:
        owner_uuid = _valid_uuid(owner)
        if owner_uuid is None:
            return 0

        async with self.pool.acquire() as conn:

            total = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM knowledge_base
                WHERE owner=$1
                """,
                owner_uuid,
            )

            return total if total else 0

    @staticmethod
    def _to_kb(row: asyncpg.Record) -> KnowledgeBase:
        """将数据库行转换为 KnowledgeBase 对象"""
        return KnowledgeBase(
            id=str(row["id"]),
            owner=row["owner"],
            name=row["name"],
            description=row["description"],
            is_public=row["is_public"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
