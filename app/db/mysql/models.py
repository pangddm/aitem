from sqlalchemy import Column, Integer, String

from app.db.mysql.database import Base


class User(Base):

    __tablename__ = "users"


    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
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