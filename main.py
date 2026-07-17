from contextlib import asynccontextmanager
from app.db.init_db import init_database,init_mysql
from fastapi import FastAPI

from app.db.postgres import postgres
from app.db.neo4j import neo4j
from app.llm.embedding.factory import get_embedding

# 🌟 1. 在这里导入你的 chat 路由（请根据你路由文件的实际路径修改，比如 app.routers.chat）
from app.api.chat import router as chat_router 
from app.api.auth import router as auth_router
from app.api.document import router as document_router

embedding = get_embedding()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await postgres.connect()
    init_mysql()
    await neo4j.connect()
    await init_database(postgres.pool)
    yield
    await embedding.close()
    await postgres.close()
    await neo4j.close()


app = FastAPI(
    lifespan=lifespan
)

# 🌟 2. 在这里把路由注册到 app 上！
app.include_router(chat_router)
app.include_router(auth_router)
app.include_router(document_router)
# 💡 如果你以后想让所有接口都带上统一前缀（比如 /api/chat），可以改成这样写：
# app.include_router(chat_router, prefix="/api")