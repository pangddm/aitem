import asyncpg
from dotenv import load_dotenv
import os
load_dotenv()

EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM"))
# ⚠️ 先确认 Jina 返回的向量维度，如果不是 2048，
# 改成实际维度，例如 1024。


async def init_database(
    pool: asyncpg.Pool
):
    """
    初始化 PostgreSQL 数据库
    """

    async with pool.acquire() as conn:

        # ----------------------------
        # 安装 pgvector
        # ----------------------------
        await conn.execute("""
            CREATE EXTENSION IF NOT EXISTS vector;
        """)

        # ----------------------------
        # Memory 表
        # ----------------------------
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS memory (

                id UUID PRIMARY KEY,

                owner TEXT NOT NULL,

                type TEXT NOT NULL,

                content TEXT NOT NULL,

                summary TEXT,

                source TEXT NOT NULL,

                entities TEXT[],

                importance REAL DEFAULT 0.5,

                metadata JSONB,

                embedding VECTOR({EMBEDDING_DIM}) NOT NULL,

                created_at TIMESTAMP NOT NULL,

                updated_at TIMESTAMP NOT NULL

            );
        """)

        # ----------------------------
        # 普通索引
        # ----------------------------
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

        # ----------------------------
        # Vector Index (HNSW)
        # PostgreSQL 16+/pgvector 推荐
        # ----------------------------
        # await conn.execute("""
        #     CREATE INDEX IF NOT EXISTS idx_memory_embedding
        #     ON memory
        #     USING hnsw (embedding vector_cosine_ops);
        # """)

    print("Database initialized.")