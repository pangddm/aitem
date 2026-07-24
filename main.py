from contextlib import asynccontextmanager
from app.db.init_db import init_database,init_mysql
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.db.postgres import postgres
from app.db.neo4j import neo4j
from app.llm.embedding.factory import get_embedding

# 🌟 路由导入
from app.api.chat import router as chat_router 
from app.api.auth import router as auth_router
from app.api.document import router as document_router
from app.api.knowledge import router as knowledge_router
from app.api.conversation import router as conversation_router
from app.api.conversation import host_router

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


app = FastAPI(lifespan=lifespan)

# 🌟 挂载静态文件
app.mount("/static", StaticFiles(directory="web/static"), name="static")


@app.get("/")
async def root():
    """返回前端首页"""
    return FileResponse("web/static/index.html")

# 🌟 注册路由
app.include_router(chat_router)
app.include_router(auth_router)
app.include_router(document_router)
app.include_router(knowledge_router)
app.include_router(conversation_router)
app.include_router(host_router)
