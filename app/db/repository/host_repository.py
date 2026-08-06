"""
主机持久化 Repository（PostgreSQL）

替代 Redis 中的 host_list 存储。
密码使用 AES 加密后存储，不再明文保存。
"""
from __future__ import annotations

import base64
import os
from datetime import datetime
from uuid import UUID, uuid4

import asyncpg
from cryptography.fernet import Fernet
from dotenv import load_dotenv

from app.db.postgres import postgres

load_dotenv()


def _now() -> datetime:
    return datetime.utcnow()


def _valid_uuid(value: str) -> UUID | None:
    """安全地将字符串转为 UUID，无效则返回 None"""
    try:
        return UUID(value)
    except (ValueError, AttributeError, TypeError):
        return None


def _get_cipher() -> Fernet:
    """获取加密器（密钥从环境变量读取，自动生成并持久化）"""
    key = os.getenv("HOST_ENCRYPTION_KEY", "")
    if not key:
        # 自动生成密钥并保存到 .env（首次运行）
        key = Fernet.generate_key().decode()
        # 尝试写入 .env
        try:
            env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), ".env")
            with open(env_path, "a", encoding="utf-8") as f:
                f.write(f"\nHOST_ENCRYPTION_KEY={key}\n")
        except Exception:
            pass
        os.environ["HOST_ENCRYPTION_KEY"] = key
    return Fernet(key.encode())


def encrypt_password(password: str) -> str:
    """加密主机密码"""
    if not password:
        return ""
    return _get_cipher().encrypt(password.encode()).decode()


def decrypt_password(encrypted: str) -> str:
    """解密主机密码"""
    if not encrypted:
        return ""
    try:
        return _get_cipher().decrypt(encrypted.encode()).decode()
    except Exception:
        return ""


class HostRepository:
    """主机 CRUD（PostgreSQL）"""

    async def create(
        self,
        owner: str,
        name: str,
        host: str,
        port: int,
        username: str,
        password: str,
    ) -> dict:
        """添加主机（密码加密存储）"""
        owner_uuid = _valid_uuid(owner)
        if owner_uuid is None:
            return {"id": "", "error": "invalid user_id"}

        host_id = str(uuid4())
        now = _now()
        password_encrypted = encrypt_password(password)

        async with postgres.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO host
                    (id, owner, name, host, port, username, password_encrypted, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                UUID(host_id),
                owner_uuid,
                name,
                host,
                port,
                username,
                password_encrypted,
                now,
                now,
            )

        return {
            "id": host_id,
            "name": name,
            "host": host,
            "port": port,
            "username": username,
            "created_at": now.isoformat(),
        }

    async def list_by_owner(self, owner: str) -> list[dict]:
        """获取用户的所有主机（不返回密码）"""
        owner_uuid = _valid_uuid(owner)
        if owner_uuid is None:
            return []

        async with postgres.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, name, host, port, username, created_at
                FROM host
                WHERE owner = $1
                ORDER BY created_at DESC
                """,
                owner_uuid,
            )

        return [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "host": r["host"],
                "port": r["port"],
                "username": r["username"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]

    async def get(self, host_id: str, owner: str) -> dict | None:
        """获取单个主机（含解密密码，仅内部使用）"""
        owner_uuid = _valid_uuid(owner)
        if owner_uuid is None:
            return None

        async with postgres.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, name, host, port, username, password_encrypted, created_at
                FROM host
                WHERE id = $1 AND owner = $2
                """,
                UUID(host_id),
                owner_uuid,
            )

        if row is None:
            return None

        return {
            "id": str(row["id"]),
            "name": row["name"],
            "host": row["host"],
            "port": row["port"],
            "username": row["username"],
            "password": decrypt_password(row["password_encrypted"]),
            "created_at": row["created_at"].isoformat(),
        }

    async def delete(self, host_id: str, owner: str) -> None:
        """删除主机"""
        owner_uuid = _valid_uuid(owner)
        if owner_uuid is None:
            return

        async with postgres.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM host WHERE id = $1 AND owner = $2",
                UUID(host_id),
                owner_uuid,
            )


# 全局单例
host_repo = HostRepository()