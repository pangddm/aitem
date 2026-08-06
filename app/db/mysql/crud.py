import hashlib
import os
from uuid import uuid4

from app.db.mysql.database import SessionLocal
from app.db.mysql.models import User


def _hash_password(password: str, salt: str = None) -> tuple:
    """SHA-256 哈希密码，返回 (hash, salt)"""
    if salt is None:
        salt = os.urandom(16).hex()
    h = hashlib.sha256((password + salt).encode()).hexdigest()
    return h, salt


def get_user(username: str):
    db = SessionLocal()
    user = db.query(User).filter(
        User.username == username
    ).first()
    db.close()
    return user


def get_user_by_id(user_id: str):
    db = SessionLocal()
    user = db.query(User).filter(
        User.id == user_id
    ).first()
    db.close()
    return user


def create_user(username: str, password: str):
    db = SessionLocal()
    pw_hash, salt = _hash_password(password)
    user_id = str(uuid4())
    user = User(
        id=user_id,
        username=username,
        password=pw_hash,
        salt=salt,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()

    # PostgreSQL app_user 同步已移至 app/api/auth.py 的 register/login 中
    # 避免在同步代码中操作异步 pool 导致事件循环冲突

    return user


def verify_user(username: str, password: str):
    db = SessionLocal()
    user = db.query(User).filter(
        User.username == username
    ).first()
    db.close()
    if not user:
        return None
    # 验证密码哈希
    h, _ = _hash_password(password, user.salt)
    if h != user.password:
        return None

    # PostgreSQL app_user 同步已移至 app/api/auth.py 的 login 中
    # 避免在同步代码中操作异步 pool 导致事件循环冲突

    return user