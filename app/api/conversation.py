"""
会话管理 API

支持多轮对话历史：创建、列表、查看、删除、重命名。
数据存储在 Redis 中，与 SessionMemory 共享同一 Redis 实例。
"""

import json
from datetime import datetime, timezone
from uuid import uuid4

import redis
import os
from dotenv import load_dotenv
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

load_dotenv()

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])

TTL = int(os.getenv("REDIS_TTL", 86400 * 7))  # 默认 7 天


def _conv_list_key(user_id: str) -> str:
    return f"conv_list:{user_id}"


def _msgs_key(conv_id: str) -> str:
    return f"conv_msgs:{conv_id}"


@router.get("")
async def list_conversations(user_id: str = Query(...)):
    """获取用户的所有对话列表（按更新时间倒序）"""
    data = r.get(_conv_list_key(user_id))
    if not data:
        return {"success": True, "data": []}
    conversations = json.loads(data)
    conversations.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return {"success": True, "data": conversations}


@router.post("")
async def create_conversation(
    user_id: str = Query(...),
    title: str = Query("新对话"),
):
    """创建新对话"""
    conv_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    conv = {
        "id": conv_id,
        "title": title,
        "created_at": now,
        "updated_at": now,
    }

    key = _conv_list_key(user_id)
    data = r.get(key)
    conversations = json.loads(data) if data else []
    conversations.append(conv)
    r.set(key, json.dumps(conversations), ex=TTL)

    # 初始化空消息
    r.set(_msgs_key(conv_id), json.dumps([]), ex=TTL)

    return {"success": True, "data": conv}


@router.get("/{conv_id}")
async def get_conversation(conv_id: str):
    """获取对话的所有消息"""
    data = r.get(_msgs_key(conv_id))
    messages = json.loads(data) if data else []
    return {"success": True, "data": messages}


@router.delete("/{conv_id}")
async def delete_conversation(conv_id: str, user_id: str = Query(...)):
    """删除对话"""
    r.delete(_msgs_key(conv_id))

    key = _conv_list_key(user_id)
    data = r.get(key)
    if data:
        conversations = json.loads(data)
        conversations = [c for c in conversations if c["id"] != conv_id]
        r.set(key, json.dumps(conversations), ex=TTL)

    return {"success": True}


@router.put("/{conv_id}")
async def rename_conversation(
    conv_id: str,
    title: str = Query(...),
    user_id: str = Query(...),
):
    """重命名对话"""
    key = _conv_list_key(user_id)
    data = r.get(key)
    if data:
        conversations = json.loads(data)
        for conv in conversations:
            if conv["id"] == conv_id:
                conv["title"] = title
                break
        r.set(key, json.dumps(conversations), ex=TTL)

    return {"success": True}


# ──── 辅助函数（供 chat API 内部调用）────

def save_message(conv_id: str, role: str, content: str, user_id: str = None, thinking_chain: list = None):
    """在指定对话中追加一条消息

    Args:
        thinking_chain: 思考链数据列表（仅 assistant 消息有）
    """
    key = _msgs_key(conv_id)
    data = r.get(key)
    messages = json.loads(data) if data else []
    msg = {
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if thinking_chain:
        msg["thinking_chain"] = thinking_chain
    messages.append(msg)
    r.set(key, json.dumps(messages), ex=TTL)

    # 如果第一条用户消息，自动更新标题
    user_msgs = [m for m in messages if m["role"] == "user"]
    if len(user_msgs) == 1 and role == "user":
        auto_title = content[:30].replace("\n", " ").strip()
        _update_title_internal(conv_id, auto_title, user_id)

    # 更新 updated_at
    _touch_conv(conv_id, user_id)


def _touch_conv(conv_id: str, user_id: str = None):
    """更新对话的 updated_at 时间戳"""
    now = datetime.now(timezone.utc).isoformat()
    if user_id:
        # 直接定位用户的对话列表，避免全量扫描
        key = _conv_list_key(user_id)
        data = r.get(key)
        if data:
            conversations = json.loads(data)
            for conv in conversations:
                if conv["id"] == conv_id:
                    conv["updated_at"] = now
                    r.set(key, json.dumps(conversations), ex=TTL)
                    return
    # 回退：扫描所有用户（兼容旧调用）
    for key in r.scan_iter("conv_list:*"):
        data = r.get(key)
        if data:
            conversations = json.loads(data)
            updated = False
            for conv in conversations:
                if conv["id"] == conv_id:
                    conv["updated_at"] = now
                    updated = True
                    break
            if updated:
                r.set(key, json.dumps(conversations), ex=TTL)
                break


def _update_title_internal(conv_id: str, title: str, user_id: str = None):
    """自动更新对话标题"""
    if user_id:
        key = _conv_list_key(user_id)
        data = r.get(key)
        if data:
            conversations = json.loads(data)
            for conv in conversations:
                if conv["id"] == conv_id and conv["title"] == "新对话":
                    conv["title"] = title
                    r.set(key, json.dumps(conversations), ex=TTL)
                    return
    # 回退：扫描所有用户
    for key in r.scan_iter("conv_list:*"):
        data = r.get(key)
        if data:
            conversations = json.loads(data)
            for conv in conversations:
                if conv["id"] == conv_id and conv["title"] == "新对话":
                    conv["title"] = title
                    r.set(key, json.dumps(conversations), ex=TTL)
                    return


# ══════════════════════════════════════════════════════════
#  主机管理 API（独立 router，复用同一 Redis 实例）
# ══════════════════════════════════════════════════════════

from uuid import uuid4 as _uuid4
from pydantic import BaseModel

host_router = APIRouter(prefix="/hosts", tags=["hosts"])


def _host_list_key(user_id: str) -> str:
    return f"host_list:{user_id}"


class HostCreate(BaseModel):
    name: str
    host: str
    port: int = 22
    username: str
    password: str = ""


@host_router.get("")
async def list_hosts(user_id: str = Query(...)):
    """获取用户的所有主机列表"""
    data = r.get(_host_list_key(user_id))
    if not data:
        return {"success": True, "data": []}
    hosts = json.loads(data)
    for h in hosts:
        h.pop("password", None)  # 列表不返回密码
    return {"success": True, "data": hosts}


@host_router.post("")
async def create_host(host: HostCreate, user_id: str = Query(...)):
    """添加一个主机"""
    host_id = str(_uuid4())
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": host_id,
        "name": host.name,
        "host": host.host,
        "port": host.port,
        "username": host.username,
        "password": host.password,
        "created_at": now,
    }
    key = _host_list_key(user_id)
    data = r.get(key)
    hosts = json.loads(data) if data else []
    hosts.append(record)
    r.set(key, json.dumps(hosts), ex=TTL)
    record.pop("password", None)
    return {"success": True, "data": record}


@host_router.delete("/{host_id}")
async def delete_host(host_id: str, user_id: str = Query(...)):
    """删除主机"""
    key = _host_list_key(user_id)
    data = r.get(key)
    if data:
        hosts = json.loads(data)
        hosts = [h for h in hosts if h["id"] != host_id]
        r.set(key, json.dumps(hosts), ex=TTL)
    return {"success": True}


@host_router.get("/{host_id}/test")
async def test_host(host_id: str, user_id: str = Query(...)):
    """测试主机连接"""
    key = _host_list_key(user_id)
    data = r.get(key)
    if not data:
        return JSONResponse(status_code=404, content={"success": False, "message": "主机不存在"})
    hosts = json.loads(data)
    target = next((h for h in hosts if h["id"] == host_id), None)
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


def get_host_by_id(user_id: str, host_id: str) -> dict:
    """辅助函数：根据 ID 获取主机完整信息（含密码）"""
    data = r.get(_host_list_key(user_id))
    if not data:
        return None
    hosts = json.loads(data)
    return next((h for h in hosts if h["id"] == host_id), None)
