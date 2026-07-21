from __future__ import annotations

import os

import asyncpg
from dotenv import load_dotenv

load_dotenv()

EMBEDDING_DIM = int(
    os.getenv("EMBEDDING_DIM")
)


async def create_knowledge_schema(
    conn: asyncpg.Connection,
):

    # ==========================================================
    # Knowledge Base
    # ==========================================================

    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_base (

            id UUID PRIMARY KEY,

            owner TEXT NOT NULL,

            name TEXT NOT NULL,

            description TEXT,

            is_public BOOLEAN DEFAULT FALSE,

            created_at TIMESTAMP NOT NULL,

            updated_at TIMESTAMP NOT NULL

        );
        """
    )

    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_kb_owner
        ON knowledge_base(owner);
        """
    )

    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_kb_created
        ON knowledge_base(created_at DESC);
        """
    )

    # ==========================================================
    # Document
    # ==========================================================

    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS document (

            id UUID PRIMARY KEY,

            owner TEXT NOT NULL,

            kb_id UUID NOT NULL,

            filename TEXT NOT NULL,

            mime_type TEXT NOT NULL,

            file_size BIGINT NOT NULL,

            source TEXT NOT NULL,

            origin_text TEXT,

            ocr_text TEXT,

            content_hash TEXT,

            parse_status TEXT NOT NULL,

            metadata JSONB DEFAULT '{}'::jsonb,

            created_at TIMESTAMP NOT NULL,

            updated_at TIMESTAMP NOT NULL,

            CONSTRAINT fk_document_kb
            FOREIGN KEY(kb_id)
            REFERENCES knowledge_base(id)
            ON DELETE CASCADE

        );
        """
    )

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_owner
        ON document(owner);
    """)

    # 兼容已有数据库：添加 content_hash 列
    await conn.execute("""
        ALTER TABLE document
        ADD COLUMN IF NOT EXISTS content_hash TEXT;
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_kb
        ON document(kb_id);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_status
        ON document(parse_status);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_created
        ON document(created_at DESC);
    """)

    # 去重：同一用户下 content_hash 唯一（跨知识库）
    await conn.execute("""
        DROP INDEX IF EXISTS idx_document_kb_hash;
    """)
    await conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_document_owner_hash
        ON document(owner, content_hash)
        WHERE content_hash IS NOT NULL;
    """)
        # ==========================================================
    # Incident
    # ==========================================================

    await conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS incident (

            id UUID PRIMARY KEY,

            owner TEXT NOT NULL,

            kb_id UUID NOT NULL,

            document_id UUID,

            source TEXT NOT NULL,

            category TEXT NOT NULL DEFAULT 'doc',

            title TEXT NOT NULL,

            summary TEXT NOT NULL,

            symptom TEXT NOT NULL,

            root_cause TEXT NOT NULL,

            solution TEXT NOT NULL,

            keywords TEXT[] DEFAULT '{{}}',

            environment JSONB DEFAULT '{{}}'::jsonb,

            metadata JSONB DEFAULT '{{}}'::jsonb,

            embedding VECTOR({EMBEDDING_DIM}) NOT NULL,

            created_at TIMESTAMP NOT NULL,

            updated_at TIMESTAMP NOT NULL,

            CONSTRAINT fk_incident_kb
            FOREIGN KEY(kb_id)
            REFERENCES knowledge_base(id)
            ON DELETE CASCADE,

            CONSTRAINT fk_incident_document
            FOREIGN KEY(document_id)
            REFERENCES document(id)
            ON DELETE SET NULL

        );
        """
    )

    # 兼容已有数据库：添加 category 列
    await conn.execute("""
        ALTER TABLE incident
        ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'doc';
    """)

    # Parent-Child Chunking: 父上下文
    await conn.execute("""
        ALTER TABLE incident
        ADD COLUMN IF NOT EXISTS context_text TEXT DEFAULT '';
    """)

    # Owner

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_incident_owner
        ON incident(owner);
    """)

    # KB

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_incident_kb
        ON incident(kb_id);
    """)

    # Created

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_incident_created
        ON incident(created_at DESC);
    """)

    # Keyword

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_incident_keywords
        ON incident
        USING GIN(keywords);
    """)

    # Vector

    await conn.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_incident_embedding
        ON incident
        USING hnsw
        (
            embedding
            vector_cosine_ops
        );
    """)

    # ==========================================================
    # Incident Command
    # ==========================================================

    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS incident_command (

            id UUID PRIMARY KEY,

            incident_id UUID NOT NULL,

            step INTEGER NOT NULL,

            command TEXT NOT NULL,

            stdout TEXT,

            stderr TEXT,

            exit_code INTEGER NOT NULL DEFAULT 0,

            CONSTRAINT fk_command_incident
            FOREIGN KEY(incident_id)
            REFERENCES incident(id)
            ON DELETE CASCADE

        );
        """
    )

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_command_incident
        ON incident_command(incident_id);
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_command_step
        ON incident_command(step);
    """)