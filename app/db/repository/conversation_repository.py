"""
对话持久化 Repository（PostgreSQL）

替代 Redis 中的 conv_list / conv_msgs 存储。
Redis 仅作为缓存层，PostgreSQL 为持久化主库。
"""
from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID, uuid4

import asyncpg

from app.db.postgres import postgres


def _now() -> datetime:
    return datetime.utcnow()


def _valid_uuid(value: str) -> UUID | None:
    """安全地将字符串转为 UUID，无效则返回 None"""
    try:
        return UUID(value)
    except (ValueError, AttributeError, TypeError):
        return None


def _parse_thinking_chain(value) -> list:
    """POSTGRES 的 JSONB 列经 asyncpg 返回时可能是 JSON 字符串，统一解析为数组"""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


class ConversationRepository:
    """对话 CRUD（PostgreSQL）"""

    # ==========================================================
    # 对话列表
    # ==========================================================

    async def create(
        self,
        owner: str,
        title: str = "新对话",
    ) -> dict:
        """创建新对话"""
        owner_uuid = _valid_uuid(owner)
        if owner_uuid is None:
            return {"id": "", "title": title, "error": "invalid user_id"}

        conv_id = str(uuid4())
        now = _now()

        async with postgres.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO conversation (id, owner, title, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5)
                """,
                UUID(conv_id),
                owner_uuid,
                title,
                now,
                now,
            )

        return {
            "id": conv_id,
            "title": title,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

    async def list_by_owner(self, owner: str) -> list[dict]:
        """获取用户的所有对话（按更新时间倒序）"""
        owner_uuid = _valid_uuid(owner)
        if owner_uuid is None:
            return []

        async with postgres.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, title, created_at, updated_at
                FROM conversation
                WHERE owner = $1
                ORDER BY updated_at DESC
                """,
                owner_uuid,
            )

        return [
            {
                "id": str(r["id"]),
                "title": r["title"],
                "created_at": r["created_at"].isoformat(),
                "updated_at": r["updated_at"].isoformat(),
            }
            for r in rows
        ]

    async def list_by_user(self, user_id: str) -> list[dict]:
        """获取用户的所有对话（user_id 别名，等价于 list_by_owner）"""
        return await self.list_by_owner(user_id)

    async def get(self, conv_id: str) -> dict | None:
        """获取单个对话"""
        async with postgres.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, owner, title, created_at, updated_at
                FROM conversation
                WHERE id = $1
                """,
                UUID(conv_id),
            )

        if row is None:
            return None

        return {
            "id": str(row["id"]),
            "owner": str(row["owner"]),
            "title": row["title"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        }

    async def rename(self, conv_id: str, title: str) -> None:
        """重命名对话"""
        async with postgres.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE conversation
                SET title = $2, updated_at = $3
                WHERE id = $1
                """,
                UUID(conv_id),
                title,
                _now(),
            )

    async def touch(self, conv_id: str) -> None:
        """更新对话的 updated_at"""
        async with postgres.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE conversation
                SET updated_at = $2
                WHERE id = $1
                """,
                UUID(conv_id),
                _now(),
            )

    async def delete(self, conv_id: str, owner: str | None = None) -> None:
        """删除对话（级联删除消息）"""
        async with postgres.pool.acquire() as conn:
            if owner:
                await conn.execute(
                    "DELETE FROM conversation WHERE id = $1 AND owner = $2",
                    UUID(conv_id),
                    UUID(owner),
                )
            else:
                await conn.execute(
                    "DELETE FROM conversation WHERE id = $1",
                    UUID(conv_id),
                )

    # ==========================================================
    # 对话消息
    # ==========================================================

    async def add_message(
        self,
        conv_id: str,
        role: str,
        content: str,
        thinking_chain: list | None = None,
    ) -> dict:
        """追加一条消息"""
        msg_id = str(uuid4())
        now = _now()

        async with postgres.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO conversation_message
                    (id, conversation_id, role, content, thinking_chain, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                UUID(msg_id),
                UUID(conv_id),
                role,
                content,
                json.dumps(thinking_chain or []),
                now,
            )
            # 更新对话时间戳
            await conn.execute(
                """
                UPDATE conversation SET updated_at = $2 WHERE id = $1
                """,
                UUID(conv_id),
                now,
            )

        return {
            "id": msg_id,
            "role": role,
            "content": content,
            "thinking_chain": thinking_chain or [],
            "timestamp": now.isoformat(),
        }

    async def list_messages(self, conv_id: str) -> list[dict]:
        """获取对话的所有消息"""
        async with postgres.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, role, content, thinking_chain, created_at
                FROM conversation_message
                WHERE conversation_id = $1
                ORDER BY created_at
                """,
                UUID(conv_id),
            )

        return [
            {
                "id": str(r["id"]),
                "role": r["role"],
                "content": r["content"],
                "thinking_chain": _parse_thinking_chain(r["thinking_chain"]),
                "timestamp": r["created_at"].isoformat(),
            }
            for r in rows
        ]

    async def count_user_messages(self, conv_id: str) -> int:
        """统计用户消息数量（用于自动标题）"""
        async with postgres.pool.acquire() as conn:
            return await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM conversation_message
                WHERE conversation_id = $1 AND role = 'user'
                """,
                UUID(conv_id),
            )


# 全局单例
conversation_repo = ConversationRepository()