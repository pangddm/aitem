from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID, uuid4

import asyncpg

from app.knowledge.models import (
    CommandTrace,
    Incident,
    IncidentSource,
    KnowledgeCategory,
)


class IncidentRepository:

    def __init__(
        self,
        pool: asyncpg.Pool,
    ):
        self.pool = pool

    # ==========================================================
    # Row -> Model
    # ==========================================================

    @staticmethod
    def _build_incident(
        row: asyncpg.Record,
        commands: list[CommandTrace],
    ) -> Incident:

        return Incident(

            id=str(row["id"]),

            owner=row["owner"],

            kb_id=str(row["kb_id"]),

            document_id=(
                str(row["document_id"])
                if row["document_id"]
                else None
            ),

            source=IncidentSource(
                row["source"]
            ),

            category=KnowledgeCategory(
                row["category"]
            ),

            context_text=row.get("context_text") or "",

            title=row["title"],

            summary=row["summary"],

            symptom=row["symptom"],

            root_cause=row["root_cause"],

            solution=row["solution"],

            keywords=row["keywords"] or [],

            environment=row["environment"] or {},

            metadata=row["metadata"] or {},

            embedding=row["embedding"],

            created_at=row["created_at"],

            updated_at=row["updated_at"],

            commands=commands,
        )

    # ==========================================================
    # Load Commands
    # ==========================================================

    async def _load_commands(
        self,
        conn: asyncpg.Connection,
        incident_id: str,
    ) -> list[CommandTrace]:

        rows = await conn.fetch(
            """
            SELECT *

            FROM incident_command

            WHERE incident_id=$1

            ORDER BY step
            """,
            UUID(incident_id),
        )

        commands = []

        for row in rows:

            commands.append(

                CommandTrace(

                    command=row["command"],

                    stdout=row["stdout"],

                    stderr=row["stderr"],

                    exit_code=row["exit_code"],

                )

            )

        return commands
    # ==========================================================
    # Create
    # ==========================================================

    async def create(
        self,
        incident: Incident,
    ) -> None:

        async with self.pool.acquire() as conn:

            async with conn.transaction():

                await conn.execute(
                    """
                    INSERT INTO incident (

                        id,

                        owner,

                        kb_id,

                        document_id,

                        source,

                        category,

                        context_text,

                        title,

                        summary,

                        symptom,

                        root_cause,

                        solution,

                        keywords,

                        environment,

                        metadata,

                        embedding,

                        created_at,

                        updated_at

                    )

                    VALUES(

                        $1,$2,$3,$4,$5,

                        $6,$7,$8,$9,$10,

                        $11,$12,$13,$14,$15,

                        $16,$17,$18

                    )
                    """,

                    UUID(incident.id),

                    incident.owner,

                    UUID(incident.kb_id),

                    (
                        UUID(incident.document_id)
                        if incident.document_id
                        else None
                    ),

                    incident.source.value,

                    incident.category.value,

                    incident.context_text,

                    incident.title,

                    incident.summary,

                    incident.symptom,

                    incident.root_cause,

                    incident.solution,

                    incident.keywords,

                    json.dumps(
                        incident.environment
                    ),

                    json.dumps(
                        incident.metadata
                    ),

                    incident.embedding,

                    incident.created_at,

                    incident.updated_at,
                )

                for step, cmd in enumerate(
                    incident.commands,
                    start=1,
                ):

                    await conn.execute(
                        """
                        INSERT INTO incident_command(

                            id,

                            incident_id,

                            step,

                            command,

                            stdout,

                            stderr,

                            exit_code

                        )

                        VALUES(

                            $1,$2,$3,$4,$5,$6,$7

                        )
                        """,

                        uuid4(),

                        UUID(
                            incident.id
                        ),

                        step,

                        cmd.command,

                        cmd.stdout,

                        cmd.stderr,

                        cmd.exit_code,
                    )
    # ==========================================================
    # Batch Create (optimized: single transaction)
    # ==========================================================

    async def batch_create(
        self,
        incidents: list[Incident],
    ) -> None:

        if not incidents:
            return

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany(
                    """
                    INSERT INTO incident (

                        id,

                        owner,

                        kb_id,

                        document_id,

                        source,

                        category,

                        context_text,

                        title,

                        summary,

                        symptom,

                        root_cause,

                        solution,

                        keywords,

                        environment,

                        metadata,

                        embedding,

                        created_at,

                        updated_at

                    )

                    VALUES(

                        $1,$2,$3,$4,$5,

                        $6,$7,$8,$9,$10,

                        $11,$12,$13,$14,$15,

                        $16,$17,$18

                    )
                    """,
                    [
                        (
                            UUID(inc.id),
                            inc.owner,
                            UUID(inc.kb_id),
                            UUID(inc.document_id) if inc.document_id else None,
                            inc.source.value,
                            inc.category.value,
                            inc.context_text,
                            inc.title,
                            inc.summary,
                            inc.symptom,
                            inc.root_cause,
                            inc.solution,
                            inc.keywords,
                            json.dumps(inc.environment),
                            json.dumps(inc.metadata),
                            inc.embedding,
                            inc.created_at,
                            inc.updated_at,
                        )
                        for inc in incidents
                    ],
                )

                # Batch insert commands
                cmd_params = []
                for inc in incidents:
                    for step, cmd in enumerate(inc.commands, start=1):
                        cmd_params.append((
                            uuid4(),
                            UUID(inc.id),
                            step,
                            cmd.command,
                            cmd.stdout,
                            cmd.stderr,
                            cmd.exit_code,
                        ))

                if cmd_params:
                    await conn.executemany(
                        """
                        INSERT INTO incident_command(
                            id,
                            incident_id,
                            step,
                            command,
                            stdout,
                            stderr,
                            exit_code
                        )
                        VALUES(
                            $1,$2,$3,$4,$5,$6,$7
                        )
                        """,
                        cmd_params,
                    )
    # ==========================================================
    # Get
    # ==========================================================

    async def get(
        self,
        incident_id: str,
    ) -> Incident | None:

        async with self.pool.acquire() as conn:

            row = await conn.fetchrow(
                """
                SELECT *
                FROM incident
                WHERE id=$1
                """,
                UUID(incident_id),
            )

            if row is None:
                return None

            commands = await self._load_commands(
                conn, incident_id
            )

            return self._build_incident(
                row, commands
            )

    # ==========================================================
    # List by KB
    # ==========================================================

    async def list_by_kb(
        self,
        kb_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Incident], int]:

        offset = (page - 1) * page_size

        async with self.pool.acquire() as conn:

            count_row = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM incident
                WHERE kb_id=$1
                """,
                UUID(kb_id),
            )

            total = count_row if count_row else 0

            rows = await conn.fetch(
                """
                SELECT *
                FROM incident
                WHERE kb_id=$1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                UUID(kb_id),
                page_size,
                offset,
            )

            incidents = []
            for row in rows:
                commands = await self._load_commands(
                    conn, str(row["id"])
                )
                incidents.append(
                    self._build_incident(row, commands)
                )

        return incidents, total

    # ==========================================================
    # List by Document
    # ==========================================================

    async def list_by_document(
        self,
        document_id: str,
    ) -> list[Incident]:
        """获取某个文档下的所有 Incident（用于去重返回）"""

        async with self.pool.acquire() as conn:

            rows = await conn.fetch(
                """
                SELECT *
                FROM incident
                WHERE document_id=$1
                ORDER BY created_at DESC
                """,
                UUID(document_id),
            )

            incidents = []
            for row in rows:
                commands = await self._load_commands(
                    conn, str(row["id"])
                )
                incidents.append(
                    self._build_incident(row, commands)
                )

        return incidents

    # ==========================================================
    # Update
    # ==========================================================

    async def update(
        self,
        incident: Incident,
    ) -> None:

        async with self.pool.acquire() as conn:

            async with conn.transaction():

                await conn.execute(
                    """
                    UPDATE incident SET
                        category=$2,
                        context_text=$3,
                        title=$4,
                        summary=$5,
                        symptom=$6,
                        root_cause=$7,
                        solution=$8,
                        keywords=$9,
                        environment=$10,
                        metadata=$11,
                        embedding=$12,
                        updated_at=$13
                    WHERE id=$1
                    """,
                    UUID(incident.id),
                    incident.category.value,
                    incident.context_text,
                    incident.title,
                    incident.summary,
                    incident.symptom,
                    incident.root_cause,
                    incident.solution,
                    incident.keywords,
                    json.dumps(incident.environment),
                    json.dumps(incident.metadata),
                    incident.embedding,
                    incident.updated_at,
                )

                # Replace commands
                await conn.execute(
                    """
                    DELETE FROM incident_command
                    WHERE incident_id=$1
                    """,
                    UUID(incident.id),
                )

                for step, cmd in enumerate(
                    incident.commands,
                    start=1,
                ):
                    await conn.execute(
                        """
                        INSERT INTO incident_command(
                            id, incident_id, step,
                            command, stdout, stderr, exit_code
                        )
                        VALUES($1,$2,$3,$4,$5,$6,$7)
                        """,
                        uuid4(),
                        UUID(incident.id),
                        step,
                        cmd.command,
                        cmd.stdout,
                        cmd.stderr,
                        cmd.exit_code,
                    )

    # ==========================================================
    # Delete
    # ==========================================================

    async def delete(
        self,
        incident_id: str,
    ) -> None:

        async with self.pool.acquire() as conn:

            await conn.execute(
                """
                DELETE FROM incident
                WHERE id=$1
                """,
                UUID(incident_id),
            )

    # ==========================================================
    # Count by KB
    # ==========================================================

    async def count_by_kb(
        self,
        kb_id: str,
    ) -> int:

        async with self.pool.acquire() as conn:

            total = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM incident
                WHERE kb_id=$1
                """,
                UUID(kb_id),
            )

            return total if total else 0

    # ==========================================================
    # Vector Similarity Search
    # ==========================================================

    async def similarity_search(
        self,
        kb_id: str,
        embedding: list[float],
        top_k: int = 10,
    ) -> list[Incident]:

        async with self.pool.acquire() as conn:

            rows = await conn.fetch(
                f"""
                SELECT *,
                    1 - (embedding <=> $2::vector) AS score
                FROM incident
                WHERE kb_id=$1
                ORDER BY embedding <=> $2::vector
                LIMIT $3
                """,
                UUID(kb_id),
                embedding,
                top_k,
            )

        results = []
        for row in rows:
            incident = self._build_incident(row, [])
            incident.score = float(row["score"])
            results.append(incident)

        return results

    # ==========================================================
    # Keyword Search
    # ==========================================================

    async def keyword_search(
        self,
        kb_id: str,
        query: str,
        top_k: int = 10,
    ) -> list[Incident]:

        keywords = self._extract_keywords(query)

        if not keywords:
            return []

        tsquery = " | ".join(
            f"{k}:*" for k in keywords
        )

        async with self.pool.acquire() as conn:

            rows = await conn.fetch(
                """
                SELECT *,
                    ts_rank(
                        to_tsvector('simple',
                            coalesce(title,'') || ' ' ||
                            coalesce(summary,'') || ' ' ||
                            coalesce(symptom,'') || ' ' ||
                            coalesce(root_cause,'') || ' ' ||
                            coalesce(solution,'')
                        ),
                        to_tsquery('simple', $2)
                    ) AS score
                FROM incident
                WHERE kb_id=$1
                  AND to_tsvector('simple',
                      coalesce(title,'') || ' ' ||
                      coalesce(summary,'') || ' ' ||
                      coalesce(symptom,'') || ' ' ||
                      coalesce(root_cause,'') || ' ' ||
                      coalesce(solution,'')
                  ) @@ to_tsquery('simple', $2)
                ORDER BY score DESC
                LIMIT $3
                """,
                UUID(kb_id),
                tsquery,
                top_k,
            )

        results = []
        for row in rows:
            incident = self._build_incident(row, [])
            incident.score = float(
                row["score"]
            ) if row["score"] else 0.0
            results.append(incident)

        return results

    # ==========================================================
    # Hybrid Search (Vector + Keyword)
    # ==========================================================

    async def hybrid_search(
        self,
        kb_id: str,
        query: str,
        embedding: list[float],
        top_k: int = 10,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ) -> list[Incident]:

        keywords = self._extract_keywords(query)

        if not keywords:
            return await self.similarity_search(
                kb_id=kb_id,
                embedding=embedding,
                top_k=top_k,
            )

        tsquery = " | ".join(
            f"{k}:*" for k in keywords
        )

        async with self.pool.acquire() as conn:

            rows = await conn.fetch(
                f"""
                SELECT *,
                    ({vector_weight} * (1 - (embedding <=> $2::vector)))
                    +
                    ({keyword_weight} *
                        coalesce(
                            ts_rank(
                                to_tsvector('simple',
                                    coalesce(title,'') || ' ' ||
                                    coalesce(summary,'') || ' ' ||
                                    coalesce(symptom,'') || ' ' ||
                                    coalesce(root_cause,'') || ' ' ||
                                    coalesce(solution,'')
                                ),
                                to_tsquery('simple', $3)
                            ),
                            0
                        )
                    ) AS score
                FROM incident
                WHERE kb_id=$1
                ORDER BY score DESC
                LIMIT $4
                """,
                UUID(kb_id),
                embedding,
                tsquery,
                top_k,
            )

        results = []
        for row in rows:
            score = float(row["score"]) if row["score"] else 0.0
            if score > 0:
                incident = self._build_incident(row, [])
                incident.score = score
                results.append(incident)

        return results

    # ==========================================================
    # Batch Create
    # ==========================================================

    async def batch_create(
        self,
        incidents: list[Incident],
    ) -> None:

        if not incidents:
            return

        async with self.pool.acquire() as conn:

            async with conn.transaction():

                for incident in incidents:
                    await conn.execute(
                        """
                        INSERT INTO incident (
                            id, owner, kb_id, document_id,
                            source, category, context_text,
                            title, summary, symptom,
                            root_cause, solution, keywords,
                            environment, metadata, embedding,
                            created_at, updated_at
                        )
                        VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,
                               $11,$12,$13,$14,$15,$16,$17,$18)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        UUID(incident.id),
                        incident.owner,
                        UUID(incident.kb_id),
                        (
                            UUID(incident.document_id)
                            if incident.document_id
                            else None
                        ),
                        incident.source.value,
                        incident.category.value,
                        incident.context_text,
                        incident.title,
                        incident.summary,
                        incident.symptom,
                        incident.root_cause,
                        incident.solution,
                        incident.keywords,
                        json.dumps(incident.environment),
                        json.dumps(incident.metadata),
                        incident.embedding,
                        incident.created_at,
                        incident.updated_at,
                    )

                    for step, cmd in enumerate(
                        incident.commands,
                        start=1,
                    ):
                        await conn.execute(
                            """
                            INSERT INTO incident_command(
                                id, incident_id, step,
                                command, stdout, stderr, exit_code
                            )
                            VALUES($1,$2,$3,$4,$5,$6,$7)
                            ON CONFLICT DO NOTHING
                            """,
                            uuid4(),
                            UUID(incident.id),
                            step,
                            cmd.command,
                            cmd.stdout,
                            cmd.stderr,
                            cmd.exit_code,
                        )

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _extract_keywords(
        query: str,
    ) -> list[str]:

        import re

        tokens = re.findall(
            r"[a-zA-Z0-9\u4e00-\u9fff]+",
            query.lower(),
        )

        # Filter out common stop words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were",
            "be", "been", "being", "have", "has", "had",
            "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "shall", "can",
            "to", "of", "in", "for", "on", "with", "at",
            "by", "from", "as", "into", "through", "during",
            "before", "after", "above", "below", "between",
            "and", "but", "or", "nor", "nor", "not", "so", "yet",
            "both", "either", "neither",
            "this", "that", "these", "those",
            "it", "its", "they", "them", "their",
            "我", "你", "他", "她", "它",
            "的", "了", "在", "是", "我",
            "有", "和", "就", "不", "人",
            "都", "一", "一个", "上", "也",
            "很", "到", "说", "要", "去",
            "你", "会", "着", "没有", "看",
            "好", "自己", "这",
        }

        return [
            t for t in tokens
            if t not in stop_words
        ]