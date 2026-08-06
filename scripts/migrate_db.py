"""
数据库迁移脚本：为 users 表添加 salt 字段和 UUID 主键
运行方式: python scripts/migrate_db.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.mysql.database import engine


def migrate():
    with engine.connect() as conn:
        # 1. 检查 salt 列是否已存在
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

        # 2. 检查 password 列长度是否足够（SHA-256 哈希为 64 字符）
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

        # 3. 检查 id 列（UUID 主键）是否已存在
        result = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME = 'users' "
            "AND COLUMN_NAME = 'id'"
        ))
        id_exists = result.scalar() > 0

        if id_exists:
            print("[迁移] id 字段已存在，跳过")
        else:
            # 添加 id 列（UUID 字符串），并填充现有用户
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN id VARCHAR(36) NULL"
            ))
            # 为现有用户生成 UUID（使用 MySQL 的 UUID() 函数）
            conn.execute(text(
                "UPDATE users SET id = REPLACE(UUID(), '-', '') WHERE id IS NULL"
            ))
            # 设置为主键
            conn.execute(text(
                "ALTER TABLE users MODIFY COLUMN id VARCHAR(36) NOT NULL"
            ))
            conn.execute(text(
                "ALTER TABLE users ADD PRIMARY KEY (id)"
            ))
            conn.commit()
            print("[迁移] 已添加 id 列并设置为主键")

    print("[迁移] 数据库迁移完成")


if __name__ == "__main__":
    migrate()