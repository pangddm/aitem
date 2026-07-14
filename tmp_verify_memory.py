import asyncio
from app.db.postgres import postgres

async def main():
    await postgres.connect()
    async with postgres.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, owner, content, type, importance FROM memory WHERE owner = $1 ORDER BY created_at DESC LIMIT 5",
            "wxm",
        )
        print([dict(r) for r in rows])

asyncio.run(main())
