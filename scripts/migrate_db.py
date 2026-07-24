"""
数据库迁移脚本：为 users 表添加 salt 字段
运行方式: python scripts/migrate_db.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.mysql.database import engine


def migrate():
    with engine.connect() as conn:
        # 检查 salt 列是否已存在
        result = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME = 'users' "
            "AND COLUMN_NAME = 'salt'"
        ))
        exists = result.scalar() > 0

        if exists:
            print("[迁移] salt 字段已存在，跳过")
        else:
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN salt VARCHAR(32) NOT NULL DEFAULT ''"
            ))
            conn.commit()
            print("[迁移] 已添加 salt 字段")

        # 检查 password 列长度是否足够（SHA-256 哈希为 64 字符）
        result = conn.execute(text(
            "SELECT CHARACTER_MAXIMUM_LENGTH FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME = 'users' "
            "AND COLUMN_NAME = 'password'"
        ))
        length = result.scalar()
        if length and length < 255:
            conn.execute(text(
                "ALTER TABLE users MODIFY COLUMN password VARCHAR(255) NOT NULL"
            ))
            conn.commit()
            print("[迁移] 已扩展 password 字段长度为 255")

    print("[迁移] 数据库迁移完成")


if __name__ == "__main__":
    migrate()