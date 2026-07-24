"""
密码批量哈希脚本：将现有用户的明文密码转换为 SHA-256 哈希
运行方式: python scripts/hash_passwords.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hashlib
from sqlalchemy import text
from app.db.mysql.database import engine


def hash_password(password: str, salt: str = None) -> tuple:
    """SHA-256 哈希密码，返回 (hash, salt)"""
    if salt is None:
        salt = os.urandom(16).hex()
    h = hashlib.sha256((password + salt).encode()).hexdigest()
    return h, salt


def migrate_passwords():
    with engine.connect() as conn:
        # 查询所有用户
        result = conn.execute(text("SELECT id, username, password, salt FROM users"))
        users = result.fetchall()

        updated = 0
        for user in users:
            uid, username, password, salt = user

            # 如果 salt 已存在且非空，说明已经哈希过，跳过
            if salt and salt.strip():
                continue

            # 将明文密码哈希
            pw_hash, new_salt = hash_password(password)
            conn.execute(
                text("UPDATE users SET password = :pw, salt = :salt WHERE id = :uid"),
                {"pw": pw_hash, "salt": new_salt, "uid": uid},
            )
            updated += 1
            print(f"[哈希] 用户 {username} (id={uid}) 密码已哈希")

        conn.commit()
        print(f"\n[哈希] 完成，共处理 {updated} 个用户")


if __name__ == "__main__":
    migrate_passwords()