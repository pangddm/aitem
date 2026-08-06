"""
会话管理 API

对话和主机数据持久化到 PostgreSQL，Redis 仅作为缓存层。
"""

import json
from datetime import datetime, timezone
from uuid import uuid4

import redis
import os
from dotenv import load_dotenv
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.db.repository.conversation_repository import conversation_repo
from app.db.repository.host_repository import host_repo

load_dotenv()

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])

TTL = int(os.getenv("REDIS_TTL", 86400 * 7))  # 缓存 TTL 7 天


def _conv_list_key(user_id: str) -> str:
    return f"conv_list:{user_id}"


def _msgs_key(conv_id: str) -> str:
    return f"conv_msgs:{conv_id}"


@router.get("")
async def list_conversations(user_id: str = Query(...)):
    """获取用户的所有对话列表（按更新时间倒序）"""
    # 优先从 PostgreSQL 读取（持久化主库）
    conversations = await conversation_repo.list_by_owner(user_id)
    return {"success": True, "data": conversations}


@router.post("")
async def create_conversation(
    user_id: str = Query(...),
    title: str = Query("新对话"),
):
    """创建新对话"""
    conv = await conversation_repo.create(user_id, title)
    return {"success": True, "data": conv}


@router.get("/{conv_id}")
async def get_conversation(conv_id: str):
    """获取对话的所有消息"""
    messages = await conversation_repo.list_messages(conv_id)
    return {"success": True, "data": messages}


@router.delete("/{conv_id}")
async def delete_conversation(conv_id: str, user_id: str = Query(...)):
    """删除对话"""
    await conversation_repo.delete(conv_id, owner=user_id)
    # 清理 Redis 缓存（消息 + 对话列表）
    r.delete(_msgs_key(conv_id))
    r.delete(_conv_list_key(user_id))
    return {"success": True}


@router.put("/{conv_id}")
async def rename_conversation(
    conv_id: str,
    title: str = Query(...),
    user_id: str = Query(...),
):
    """重命名对话"""
    await conversation_repo.rename(conv_id, title)
    return {"success": True}


# ──── 辅助函数（供 chat API 内部调用）────

async def save_message(conv_id: str, role: str, content: str, user_id: str = None, thinking_chain: list = None):
    """在指定对话中追加一条消息（持久化到 PostgreSQL）"""
    msg = await conversation_repo.add_message(
        conv_id, role, content, thinking_chain
    )

    # 如果第一条用户消息，自动更新标题
    if role == "user":
        user_count = await conversation_repo.count_user_messages(conv_id)
        if user_count == 1:
            auto_title = content[:30].replace("\n", " ").strip()
            await conversation_repo.rename(conv_id, auto_title)

    return msg


# ══════════════════════════════════════════════════════════
#  主机管理 API（持久化到 PostgreSQL，密码加密存储）
# ══════════════════════════════════════════════════════════

from uuid import uuid4 as _uuid4
from pydantic import BaseModel

host_router = APIRouter(prefix="/hosts", tags=["hosts"])


class HostCreate(BaseModel):
    name: str
    host: str
    port: int = 22
    username: str
    password: str = ""


@host_router.get("")
async def list_hosts(user_id: str = Query(...)):
    """获取用户的所有主机列表（不返回密码）"""
    hosts = await host_repo.list_by_owner(user_id)
    return {"success": True, "data": hosts}


@host_router.post("")
async def create_host(host: HostCreate, user_id: str = Query(...)):
    """添加一个主机（密码加密存储）"""
    record = await host_repo.create(
        owner=user_id,
        name=host.name,
        host=host.host,
        port=host.port,
        username=host.username,
        password=host.password,
    )
    return {"success": True, "data": record}


@host_router.delete("/{host_id}")
async def delete_host(host_id: str, user_id: str = Query(...)):
    """删除主机"""
    await host_repo.delete(host_id, user_id)
    return {"success": True}


@host_router.get("/{host_id}/test")
async def test_host(host_id: str, user_id: str = Query(...)):
    """测试主机连接"""
    target = await host_repo.get(host_id, user_id)
    if not target:
        return JSONResponse(status_code=404, content={"success": False, "message": "主机不存在"})
    try:
        from app.tools.ssh_client import execute_command
        result = execute_command(
            "echo ok",
            host=target["host"],
            port=target["port"],
            username=target["username"],
            password=target["password"],
        )
        return {"success": True, "message": "连接成功", "output": result.strip()}
    except Exception as e:
        return {"success": False, "message": f"连接失败: {e}"}


async def get_host_by_id(user_id: str, host_id: str) -> dict:
    """辅助函数：根据 ID 获取主机完整信息（含解密密码）"""
    return await host_repo.get(host_id, user_id)