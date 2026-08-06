import traceback
from datetime import datetime

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.db.mysql.crud import (
    create_user,
    get_user,
    get_user_by_id,
    verify_user,
)
from app.db.postgres import postgres

router = APIRouter()


async def _ensure_pg_user(user_id: str, username: str, password_hash: str, salt: str):
    """确保 PostgreSQL app_user 表中存在该用户记录"""
    print(f"[ensure_pg_user] start user_id={user_id}, username={username}", flush=True)
    print(f"[ensure_pg_user] postgres.pool={postgres.pool}", flush=True)
    if postgres.pool is None:
        print("[ensure_pg_user] postgres.pool is None!", flush=True)
        return
    async with postgres.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM app_user WHERE id = $1",
            user_id,
        )
        if row is None:
            await conn.execute(
                """
                INSERT INTO app_user (id, username, password_hash, salt, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (id) DO NOTHING
                """,
                user_id,
                username,
                password_hash,
                salt,
                datetime.utcnow(),
                datetime.utcnow(),
            )
            print(f"[ensure_pg_user] inserted app_user: {user_id}", flush=True)
        else:
            print(f"[ensure_pg_user] app_user exists: {user_id}", flush=True)


@router.post("/register")
async def register(data: dict):
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return {
            "success": False,
            "message": "用户名和密码不能为空",
        }

    # 查询用户名是否存在
    user = get_user(username)
    if user:
        return {
            "success": False,
            "message": "用户名已经存在",
        }

    user = create_user(username, password)

    # 异步同步到 PostgreSQL app_user 表
    sync_error = None
    try:
        await _ensure_pg_user(user.id, user.username, user.password, user.salt)
    except Exception as e:
        sync_error = str(e)
        traceback.print_exc()

    return {
        "success": True,
        "message": "注册成功",
        "user_id": user.id,
        "sync_error": sync_error,
        "pool_status": str(postgres.pool),
    }


@router.get("/check")
def check_user(user_id: str = Query(...)):
    """检查用户 ID 是否仍然有效（数据库可能已被清空）"""
    user = get_user_by_id(user_id)
    if user:
        return {"success": True, "username": user.username}
    return {"success": False, "message": "用户不存在"}


@router.post("/login")
async def login(data: dict):
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return {
            "success": False,
            "message": "用户名和密码不能为空",
        }

    # 先检查用户是否存在
    user = get_user(username)
    if not user:
        return {
            "success": False,
            "message": "用户不存在",
        }

    # 再验证密码
    user = verify_user(username, password)
    if not user:
        return {
            "success": False,
            "message": "密码错误",
        }

    # 异步确保 PostgreSQL app_user 表中有该用户
    try:
        await _ensure_pg_user(user.id, user.username, user.password, user.salt)
    except Exception as e:
        print(f"[login] sync app_user failed: {e}", flush=True)
        traceback.print_exc()

    return {
        "success": True,
        "user_id": user.id,
        "username": user.username,
    }