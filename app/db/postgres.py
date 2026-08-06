import asyncpg
from pgvector.asyncpg import register_vector
from typing import Optional

from app.core.config import (
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
    POSTGRES_DB,
    POSTGRES_POOL_MIN,
    POSTGRES_POOL_MAX,
)
import json


async def init_connection(conn):

    await register_vector(conn)

    await conn.set_type_codec(
        'jsonb',
        encoder=json.dumps,
        decoder=json.loads,
        schema='pg_catalog'
    )

class Postgres:

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        min_size: int = 2,
        max_size: int = 10,
    ):

        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database

        self.min_size = min_size
        self.max_size = max_size

        self.pool: Optional[asyncpg.Pool] = None


    async def connect(self):

        if self.pool is not None:
            return

        self.pool = await asyncpg.create_pool(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            min_size=self.min_size,
            max_size=self.max_size,
            init=init_connection,
        )

        print("PostgreSQL connected.")

    async def close(self):

        if self.pool is not None:

            await self.pool.close()

            self.pool = None

            print("PostgreSQL closed.")


postgres = Postgres(
    host=POSTGRES_HOST,
    port=POSTGRES_PORT,
    user=POSTGRES_USER,
    password=POSTGRES_PASSWORD,
    database=POSTGRES_DB,
    min_size=POSTGRES_POOL_MIN,
    max_size=POSTGRES_POOL_MAX,
)