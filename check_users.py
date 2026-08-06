import asyncio, asyncpg, os
from dotenv import load_dotenv
load_dotenv()

async def check():
    conn = await asyncpg.connect(
        host=os.getenv('POSTGRES_HOST','localhost'),
        port=int(os.getenv('POSTGRES_PORT','5432')),
        user=os.getenv('POSTGRES_USER','postgres'),
        password=os.getenv('POSTGRES_PASSWORD','123456'),
        database=os.getenv('POSTGRES_DB','kubedoctor')
    )
    rows = await conn.fetch("SELECT id, username, created_at FROM app_user ORDER BY created_at DESC")
    print(f"app_user count: {len(rows)}")
    for r in rows:
        print(f"  id={r['id']}, username={r['username']}, created_at={r['created_at']}")
    await conn.close()

asyncio.run(check())