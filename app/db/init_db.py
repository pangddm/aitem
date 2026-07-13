# app/db/init_db.py

import asyncpg
import os

from dotenv import load_dotenv
from pgvector.asyncpg import register_vector

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String

load_dotenv()

EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM"))

# ----------------------------
# MySQL
# ----------------------------

MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "123456")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "Users")

MYSQL_URL = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
    f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
)

mysql_engine = create_engine(MYSQL_URL)

MysqlBase = declarative_base()


class User(MysqlBase):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)

    username = Column(String(50), unique=True, nullable=False)

    password = Column(String(255), nullable=False)


def init_mysql():
    """
    初始化 MySQL
    """
    MysqlBase.metadata.create_all(mysql_engine)
    print("MySQL initialized.")


async def init_database(pool: asyncpg.Pool):
    """
    初始化 PostgreSQL
    """

    async with pool.acquire() as conn:

        await register_vector(conn)

        await conn.execute("""
            CREATE EXTENSION IF NOT EXISTS vector;
        """)

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

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_embedding
            ON memory
            USING hnsw (embedding vector_cosine_ops);
        """)

    print("PostgreSQL initialized.")