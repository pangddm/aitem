"""
统一数据库 Schema 定义

职责划分：
- PostgreSQL：持久化主库（用户、对话、主机、知识库、记忆）
- Redis：缓存层（会话临时数据、热点数据）
- Neo4j：知识图谱（仅存图关系，不存业务数据）
- MySQL：仅保留用户认证（兼容旧代码，后续可迁移到 PostgreSQL）

所有表使用 UUID 作为主键，owner 字段统一存用户 UUID。
"""
from __future__ import annotations

import os

import asyncpg
from dotenv import load_dotenv

load_dotenv()

EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))


async def create_all_schema(conn: asyncpg.Connection) -> None:
    """创建所有 PostgreSQL 表（幂等操作）"""

    # ==========================================================
    # 1. 用户表（统一用户 ID）
    # ==========================================================
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS app_user (
            id UUID PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL DEFAULT '',
            email TEXT,
            avatar TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        );
    """)

    # ==========================================================
    # 2. 主机表（持久化，密码加密存储）
    #    必须在 conversation 之前创建，因为 conversation 引用 host(id)
    # ==========================================================
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS host (
            id UUID PRIMARY KEY,
            owner UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            host TEXT NOT NULL,
            port INTEGER NOT NULL DEFAULT 22,
            username TEXT NOT NULL,
            password_encrypted TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_host_owner
        ON host(owner);
    """)

    # ==========================================================
    # 3. 对话表（持久化，替代 Redis conv_list）
    # ==========================================================
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS conversation (
            id UUID PRIMARY KEY,
            owner UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
            title TEXT NOT NULL DEFAULT '新对话',
            host_id UUID REFERENCES host(id) ON DELETE SET NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_conversation_owner
        ON conversation(owner, updated_at DESC);
    """)

    # ==========================================================
    # 4. 对话消息表（持久化，替代 Redis conv_msgs）
    # ==========================================================
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS conversation_message (
            id UUID PRIMARY KEY,
            conversation_id UUID NOT NULL REFERENCES conversation(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
            content TEXT NOT NULL,
            thinking_chain JSONB DEFAULT '[]'::jsonb,
            created_at TIMESTAMP NOT NULL
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_msg_conversation
        ON conversation_message(conversation_id, created_at);
    """)

    # ==========================================================
    # 5. 长期记忆表（带向量）
    # ==========================================================
    await conn.execute(f"""
        CREATE TABLE IF NOT EXISTS memory (
            id UUID PRIMARY KEY,
            owner UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            summary TEXT,
            source TEXT NOT NULL CHECK (source IN ('chat', 'tool', 'document', 'system', 'k8s', 'prometheus', 'manual')),
            entities TEXT[],
            importance REAL DEFAULT 0.5,
            metadata JSONB DEFAULT '{{}}'::jsonb,
            embedding VECTOR({EMBEDDING_DIM}) NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_memory_owner
        ON memory(owner);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_memory_type
        ON memory(type);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_memory_created
        ON memory(created_at DESC);
    """)
    await conn.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_memory_embedding
        ON memory USING hnsw (embedding vector_cosine_ops);
    """)

    # ==========================================================
    # 6. 知识库表
    # ==========================================================
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_base (
            id UUID PRIMARY KEY,
            owner UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            description TEXT,
            is_public BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_kb_owner
        ON knowledge_base(owner);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_kb_created
        ON knowledge_base(created_at DESC);
    """)

    # ==========================================================
    # 7. 文档表（元数据 + 全文存 PostgreSQL）
    # ==========================================================
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS document (
            id UUID PRIMARY KEY,
            owner UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
            kb_id UUID NOT NULL REFERENCES knowledge_base(id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            mime_type TEXT NOT NULL,
            file_size BIGINT NOT NULL,
            source TEXT NOT NULL CHECK (source IN ('upload', 'manual')),
            origin_text TEXT,
            ocr_text TEXT,
            content_hash TEXT,
            parse_status TEXT NOT NULL DEFAULT 'pending'
                CHECK (parse_status IN ('pending', 'processing', 'completed', 'failed')),
            deleted_at TIMESTAMP,
            metadata JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_owner
        ON document(owner);
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
        CREATE UNIQUE INDEX IF NOT EXISTS idx_document_owner_hash
        ON document(owner, content_hash)
        WHERE content_hash IS NOT NULL;
    """)

    # ==========================================================
    # 8. 知识条目表（RAG 核心，带向量）
    # ==========================================================
    await conn.execute(f"""
        CREATE TABLE IF NOT EXISTS incident (
            id UUID PRIMARY KEY,
            owner UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
            kb_id UUID NOT NULL REFERENCES knowledge_base(id) ON DELETE CASCADE,
            document_id UUID REFERENCES document(id) ON DELETE SET NULL,
            source TEXT NOT NULL DEFAULT 'upload'
                CHECK (source IN ('upload', 'learning', 'manual')),
            category TEXT NOT NULL DEFAULT 'doc'
                CHECK (category IN ('fault', 'performance', 'config', 'change', 'doc')),
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            symptom TEXT NOT NULL DEFAULT '',
            root_cause TEXT NOT NULL DEFAULT '',
            solution TEXT NOT NULL DEFAULT '',
            deleted_at TIMESTAMP,
            keywords TEXT[] DEFAULT '{{}}',
            environment JSONB DEFAULT '{{}}'::jsonb,
            metadata JSONB DEFAULT '{{}}'::jsonb,
            context_text TEXT DEFAULT '',
            embedding VECTOR({EMBEDDING_DIM}) NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_incident_owner
        ON incident(owner);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_incident_kb
        ON incident(kb_id);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_incident_created
        ON incident(created_at DESC);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_incident_keywords
        ON incident USING GIN(keywords);
    """)
    await conn.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_incident_embedding
        ON incident USING hnsw (embedding vector_cosine_ops);
    """)

    # ==========================================================
    # 9. 命令轨迹表
    # ==========================================================
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS incident_command (
            id UUID PRIMARY KEY,
            incident_id UUID NOT NULL REFERENCES incident(id) ON DELETE CASCADE,
            step INTEGER NOT NULL,
            command TEXT NOT NULL,
            stdout TEXT,
            stderr TEXT,
            exit_code INTEGER NOT NULL DEFAULT 0
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_command_incident
        ON incident_command(incident_id);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_command_step
        ON incident_command(step);
    """)

    # ==========================================================
    # 兼容已有数据库：为旧表添加缺失的列（幂等）
    # ==========================================================

    # document 表：添加 origin_text / ocr_text（旧库可能缺失）
    await conn.execute("""
        ALTER TABLE document
        ADD COLUMN IF NOT EXISTS origin_text TEXT;
    """)
    await conn.execute("""
        ALTER TABLE document
        ADD COLUMN IF NOT EXISTS ocr_text TEXT;
    """)

    # incident 表：添加 context_text（旧库可能缺失）
    await conn.execute("""
        ALTER TABLE incident
        ADD COLUMN IF NOT EXISTS context_text TEXT DEFAULT '';
    """)

    # memory 表：添加 source CHECK 约束（旧库可能没有）
    await conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'memory_source_check'
            ) THEN
                ALTER TABLE memory
                ADD CONSTRAINT memory_source_check
                CHECK (source IN ('chat', 'tool', 'document', 'system', 'k8s', 'prometheus', 'manual'));
            END IF;
        END $$;
    """)

    # conversation 表：添加 host_id 列（旧库可能缺失）
    await conn.execute("""
        ALTER TABLE conversation
        ADD COLUMN IF NOT EXISTS host_id UUID REFERENCES host(id) ON DELETE SET NULL;
    """)

    # document 表：添加 deleted_at 列（软删除）
    await conn.execute("""
        ALTER TABLE document
        ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;
    """)

    # incident 表：添加 deleted_at 列（软删除）
    await conn.execute("""
        ALTER TABLE incident
        ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;
    """)

    # document 表：放宽 symptom/root_cause/solution 的 NOT NULL 约束
    # （旧库可能为 NOT NULL，改为有默认值的 NOT NULL 以兼容）
    await conn.execute("""
        ALTER TABLE incident
        ALTER COLUMN symptom SET DEFAULT '';
    """)
    await conn.execute("""
        ALTER TABLE incident
        ALTER COLUMN root_cause SET DEFAULT '';
    """)
    await conn.execute("""
        ALTER TABLE incident
        ALTER COLUMN solution SET DEFAULT '';
    """)

    # ==========================================================
    # updated_at 自动更新触发器（所有有 updated_at 的表）
    # ==========================================================
    await conn.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    for table_name in [
        'app_user', 'conversation', 'host', 'memory',
        'knowledge_base', 'document', 'incident',
    ]:
        await conn.execute(f"""
            DROP TRIGGER IF EXISTS trg_{table_name}_updated_at
            ON {table_name};
        """)
        await conn.execute(f"""
            CREATE TRIGGER trg_{table_name}_updated_at
                BEFORE UPDATE ON {table_name}
                FOR EACH ROW EXECUTE FUNCTION update_updated_at();
        """)
