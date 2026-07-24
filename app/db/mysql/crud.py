import hashlib
import os
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


def create_user(username: str, password: str):
    db = SessionLocal()
    pw_hash, salt = _hash_password(password)
    user = User(
        username=username,
        password=pw_hash,
        salt=salt,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
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
    if h == user.password:
        return user
    return None
