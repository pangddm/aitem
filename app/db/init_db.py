# app/db/init_db.py

import asyncpg
from dotenv import load_dotenv
from pgvector.asyncpg import register_vector

from app.db.schema import create_all_schema

load_dotenv()


def init_mysql():
    """初始化 MySQL（仅创建 users 表，兼容旧代码）"""
    from app.db.mysql.database import Base as MysqlBase, engine as mysql_engine
    from app.db.mysql.models import User
    import pymysql
    import os

    # 检查 users 表是否存在且 schema 正确
    # 如果 id 列不是 VARCHAR(36)，则删除重建
    try:
        conn = pymysql.connect(
            host=os.getenv("MYSQL_HOST", "127.0.0.1").strip(),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "root").strip(),
            password=os.getenv("MYSQL_PASSWORD", "123456").strip(),
            database=os.getenv("MYSQL_DATABASE", "Users").strip(),
            charset="utf8mb4",
            autocommit=True,
        )
        cursor = conn.cursor()
        cursor.execute("DESCRIBE users")
        columns = cursor.fetchall()
        # 检查 id 列是否为 varchar 类型
        id_col = next((c for c in columns if c[0] == "id"), None)
        if id_col and "varchar" not in (id_col[1] or "").lower():
            print("[MySQL] users 表 id 列类型错误，正在重建...")
            cursor.execute("DROP TABLE IF EXISTS users")
        conn.close()
    except Exception:
        pass  # 表不存在，create_all 会自动创建

    MysqlBase.metadata.create_all(mysql_engine)
    print("MySQL initialized.")


# ==========================================================
# PostgreSQL（统一持久化主库）
# ==========================================================

# 多 worker 串行化建表的咨询锁 key（任意固定整数）
_INIT_LOCK_KEY = 727201803
async def init_database(
    pool: asyncpg.Pool,
):
    """初始化 PostgreSQL 所有表（幂等操作）"""

    async with pool.acquire() as conn:
        await register_vector(conn)

        # pgvector 扩展
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")

        # 多 worker 启动时会并发执行 DDL；用会话级咨询锁串行化，
        # 避免 CREATE TRIGGER / INDEX 等并发竞态导致 DuplicateObjectError
        await conn.execute("SELECT pg_advisory_lock($1)", _INIT_LOCK_KEY)
        try:
            await create_all_schema(conn)
        finally:
            await conn.execute("SELECT pg_advisory_unlock($1)", _INIT_LOCK_KEY)

    print("PostgreSQL initialized.")