from sqlalchemy import Column, String

from app.db.mysql.database import Base


class User(Base):

    __tablename__ = "users"

    # 使用 UUID 字符串作为主键，与 PostgreSQL 的 app_user.id 保持一致
    id = Column(
        String(36),
        primary_key=True,
    )

    username = Column(
        String(50),
        unique=True,
        nullable=False
    )

    password = Column(
        String(255),
        nullable=False
    )

    salt = Column(
        String(32),
        nullable=False,
        default=""
    )