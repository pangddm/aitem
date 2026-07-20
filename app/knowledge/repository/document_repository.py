from __future__ import annotations

from datetime import datetime

import asyncpg

from app.knowledge.models import Document, DocumentStatus


class DocumentRepository:

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def create(
        self,
        document: Document,
    ) -> None:

        async with self.pool.acquire() as conn:

            await conn.execute(
                """
                INSERT INTO document(

                    id,
                    owner,
                    kb_id,

                    filename,
                    mime_type,
                    file_size,
                    source,

                    origin_text,
                    ocr_text,

                    parse_status,

                    metadata,

                    created_at,
                    updated_at

                )

                VALUES(

                    $1,$2,$3,

                    $4,$5,$6,$7,

                    $8,$9,

                    $10,

                    $11,

                    $12,$13
                )
                """,
                document.id,
                document.owner,
                document.kb_id,

                document.filename,
                document.mime_type,
                document.file_size,
                document.source,

                document.origin_text,
                document.ocr_text,

                document.parse_status.value,

                document.metadata,

                document.created_at,
                document.updated_at,
            )

    async def get(
        self,
        document_id: str,
    ) -> Document | None:

        async with self.pool.acquire() as conn:

            row = await conn.fetchrow(
                """
                SELECT *

                FROM document

                WHERE id=$1
                """,
                document_id,
            )

        if row is None:
            return None

        return self._convert(row)

    async def list_by_kb(
        self,
        kb_id: str,
    ) -> list[Document]:

        async with self.pool.acquire() as conn:

            rows = await conn.fetch(
                """
                SELECT *

                FROM document

                WHERE kb_id=$1

                ORDER BY created_at DESC
                """,
                kb_id,
            )

        return [
            self._convert(row)
            for row in rows
        ]

    async def update_status(
        self,
        document_id: str,
        status: DocumentStatus,
    ) -> None:

        async with self.pool.acquire() as conn:

            await conn.execute(
                """
                UPDATE document

                SET parse_status=$2

                WHERE id=$1
                """,
                document_id,
                status.value,
            )

    async def update_text(
        self,
        document_id: str,
        origin_text: str,
        ocr_text: str,
    ) -> None:

        async with self.pool.acquire() as conn:

            await conn.execute(
                """
                UPDATE document

                SET

                origin_text=$2,

                ocr_text=$3

                WHERE id=$1
                """,
                document_id,
                origin_text,
                ocr_text,
            )

    async def update(
        self,
        document: Document,
    ) -> None:

        async with self.pool.acquire() as conn:

            await conn.execute(
                """
                UPDATE document SET
                    filename=$2,
                    mime_type=$3,
                    file_size=$4,
                    source=$5,
                    origin_text=$6,
                    ocr_text=$7,
                    parse_status=$8,
                    metadata=$9,
                    updated_at=$10
                WHERE id=$1
                """,
                document.id,
                document.filename,
                document.mime_type,
                document.file_size,
                document.source,
                document.origin_text,
                document.ocr_text,
                document.parse_status.value,
                document.metadata,
                document.updated_at or datetime.utcnow(),
            )

    async def delete(
        self,
        document_id: str,
    ) -> None:

        async with self.pool.acquire() as conn:

            await conn.execute(
                """
                DELETE FROM document

                WHERE id=$1
                """,
                document_id,
            )

    async def count_by_kb(
        self,
        kb_id: str,
    ) -> int:

        async with self.pool.acquire() as conn:

            total = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM document
                WHERE kb_id=$1
                """,
                kb_id,
            )

            return total if total else 0

    async def batch_delete(
        self,
        document_ids: list[str],
    ) -> None:

        if not document_ids:
            return

        async with self.pool.acquire() as conn:

            await conn.execute(
                """
                DELETE FROM document
                WHERE id = ANY($1::uuid[])
                """,
                document_ids,
            )

    async def search_by_text(
        self,
        kb_id: str,
        query: str,
        top_k: int = 10,
    ) -> list[Document]:

        async with self.pool.acquire() as conn:

            rows = await conn.fetch(
                """
                SELECT *
                FROM document
                WHERE kb_id=$1
                  AND (
                      to_tsvector('simple',
                          coalesce(origin_text,'') || ' ' ||
                          coalesce(ocr_text,'')
                      ) @@ plainto_tsquery('simple', $2)
                  )
                ORDER BY created_at DESC
                LIMIT $3
                """,
                kb_id,
                query,
                top_k,
            )

        return [
            self._convert(row)
            for row in rows
        ]

    def _convert(
        self,
        row,
    ) -> Document:

        return Document(

            id=str(row["id"]),

            owner=row["owner"],

            kb_id=str(row["kb_id"]),

            filename=row["filename"],

            mime_type=row["mime_type"],

            file_size=row["file_size"],

            source=row["source"],

            origin_text=row["origin_text"],

            ocr_text=row["ocr_text"],

            parse_status=DocumentStatus(
                row["parse_status"]
            ),

            metadata=row["metadata"] or {},

            created_at=row["created_at"],

            updated_at=row["updated_at"],
        )