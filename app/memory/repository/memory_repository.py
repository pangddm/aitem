from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import json

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
        now = datetime.utcnow()

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
                UUID(owner),
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
        now = datetime.utcnow()

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

    async def mark_superseded(
        self,
        memory_id: str,
        superseded_by: str,
    ) -> None:
        now = datetime.utcnow()
        async with postgres.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE memory
                SET
                metadata = jsonb_set(
                    COALESCE(metadata, '{}'::jsonb),
                    '{superseded}',
                    to_jsonb($2::text)
                ),
                updated_at = $3
                WHERE id = $1
                """,
                memory_id,
                superseded_by,
                now,
            )

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

    async def mark_sync_failed(
        self,
        memory_id: str,
        sync_target: str,
        error: str,
    ) -> None:
        """标记 Neo4j 同步失败，用于后续补偿重试"""
        now = datetime.utcnow()
        async with postgres.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE memory
                SET metadata = jsonb_set(
                    COALESCE(metadata, '{}'::jsonb),
                    $2,
                    to_jsonb($3::text)
                ),
                updated_at = $4
                WHERE id = $1
                """,
                memory_id,
                f"{{sync_failed,{sync_target}}}",
                error[:500],
                now,
            )

    async def list_sync_failed(
        self,
        sync_target: str = "neo4j",
        limit: int = 50,
    ) -> list[Memory]:
        """查找 Neo4j 同步失败的 Memory，用于补偿重试"""
        async with postgres.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM memory
                WHERE metadata->'sync_failed'->>$1 IS NOT NULL
                LIMIT $2
                """,
                sync_target,
                limit,
            )
        return [self._to_memory(row) for row in rows]

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
                UUID(owner),
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

        return int(result.split()[-1])

    def _apply_forgetting(
        self,
        memory,
        now: datetime,
    ) -> float:
        if memory.similarity is None:
            return 0.0

        created_at = memory.created_at

        if isinstance(created_at, datetime):
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)

            age_days = max(0.0, (now - created_at).total_seconds() / 86400.0)
        else:
            age_days = 0.0

        recency_factor = 1.0 / (1.0 + age_days / 30.0)
        importance_factor = max(0.2, min(1.0, memory.importance))

        return round(
            float(memory.similarity) * importance_factor * recency_factor,
            6,
        )

    def _to_memory(
        self,
        row,
    ) -> Memory:
        return Memory(
            id=str(row["id"]),
            owner=row["owner"],
            type=MemoryType(row["type"]),
            content=row["content"],
            summary=row["summary"],
            source=MemorySource(row["source"]),
            entities=row["entities"] or [],
            importance=row["importance"],
            metadata=row["metadata"] or {},
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            similarity=row.get("similarity"),
        )