from contextlib import asynccontextmanager
import asyncio
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
from app.api.graph import router as graph_router

embedding = get_embedding()


async def _run_decay_loop():
    """后台定时任务：每 6 小时执行一次 Memory 衰减"""
    from app.memory.job.decay import MemoryDecayJob
    from app.memory.repository.memory_repository import MemoryRepository
    from app.memory.repository.graph_repository import GraphRepository

    memory_repo = MemoryRepository()
    graph_repo = GraphRepository(driver=neo4j.get_driver())
    decay_job = MemoryDecayJob(
        memory_repository=memory_repo,
        graph_repository=graph_repo,
    )

    while True:
        try:
            await asyncio.sleep(6 * 3600)  # 6 小时
            stats = await decay_job.run()
            print(f"[DecayJob] 衰减完成: {stats}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[DecayJob] 执行失败: {e}")
            await asyncio.sleep(60)  # 出错后 1 分钟重试


def _topo_interval():
    import os
    try:
        return max(60, int(os.getenv("TOPO_INTERVAL", "300")))
    except Exception:
        return 300


async def _k8s_owners(driver):
    """返回有 K8s 拓扑的用户 id 列表"""
    from app.memory.repository.graph_repository import GraphRepository
    lbls = GraphRepository.K8S_LABELS
    try:
        async with driver.session() as s:
            r = await s.run(
                "MATCH (u:User)-[:RELATED_TO]->(e) WHERE labels(e)[0] IN $lbls "
                "RETURN DISTINCT u.id AS id",
                lbls=list(lbls),
            )
            return [x["id"] async for x in r]
    except Exception as e:
        print(f"[TopologyIndexer] 查询用户失败: {type(e).__name__}: {e}")
        return []


async def _rebuild_owner(owner: str):
    """单个账号的定时重建：每周期读取该账号自己的间隔并重建"""
    from app.memory.graph.indexer import ClusterTopologyIndexer, get_topology_interval
    from app.memory.repository.graph_repository import GraphRepository
    from app.tools.ssh_client import execute_command
    from app.core.config import TARGET_HOST, TARGET_PORT, TARGET_USERNAME, TARGET_PASSWORD
    from app.db.neo4j import neo4j as _neo4j
    while True:
        try:
            interval = get_topology_interval(owner)
            await asyncio.sleep(interval)
            driver = _neo4j.get_driver()
            repo = GraphRepository(driver=driver)
            indexer = ClusterTopologyIndexer(driver=driver)
            stats = await indexer.rebuild(
                owner, execute_command,
                TARGET_HOST, TARGET_PORT, TARGET_USERNAME, TARGET_PASSWORD, repo,
            )
            print(f"[TopologyIndexer] 定时重建 {owner}: {stats}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[TopologyIndexer] 重建 {owner} 失败: {type(e).__name__}: {e}")
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break


async def _run_topology_loop():
    """按账号调度：每个账号按各自的间隔独立定时重建集群拓扑"""
    from app.db.neo4j import neo4j as _neo4j
    tasks: dict = {}
    print("[TopologyIndexer] 按账号定时调度已启动")
    while True:
        try:
            try:
                driver = _neo4j.get_driver()
                owners = await _k8s_owners(driver)
            except Exception:
                owners = []
            for oid in owners:
                task = tasks.get(oid)
                if task is None or task.done():
                    tasks[oid] = asyncio.create_task(_rebuild_owner(oid))
            # 清理已结束/已无账号的任务
            for oid in list(tasks):
                if tasks[oid].done():
                    del tasks[oid]
            await asyncio.sleep(30)  # 定期扫描账号列表
        except asyncio.CancelledError:
            for t in tasks.values():
                t.cancel()
            break
        except Exception as e:
            print(f"[TopologyIndexer] 调度异常: {type(e).__name__}: {e}")
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break


def _acquire_leader_lock(name: str, ttl: int = 3600) -> bool:
    """用 Redis SETNX 抢占“仅一个 worker 运行”的任务锁，返回是否抢占成功。"""
    from app.db.redis import redis_client
    try:
        key = f"kubedoctor:job-leader:{name}"
        return bool(redis_client.client.set(key, "1", nx=True, ex=ttl))
    except Exception as e:
        print(f"[Leader] 获取主节点锁失败 {name}: {type(e).__name__}: {e}")
        return True  # 降级：Redis 不可用时由当前 worker 照常运行


def _release_leader_lock(name: str) -> None:
    from app.db.redis import redis_client
    try:
        redis_client.client.delete(f"kubedoctor:job-leader:{name}")
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    await postgres.connect()
    init_mysql()
    await neo4j.connect()
    await init_database(postgres.pool)

    # 多 worker 下每个 worker 都会执行 lifespan，用 Redis 锁保证后台任务只在一个 worker 运行。
    decay_leader = _acquire_leader_lock("decay")
    topology_leader = _acquire_leader_lock("topology")
    decay_task = asyncio.create_task(_run_decay_loop()) if decay_leader else None
    topology_task = asyncio.create_task(_run_topology_loop()) if topology_leader else None
    if not decay_leader:
        print("[Leader] Memory 衰减任务由其它 worker 运行，本 worker 跳过")
    if not topology_leader:
        print("[Leader] 拓扑重建任务由其它 worker 运行，本 worker 跳过")

    yield

    # 取消后台任务
    if decay_task is not None:
        decay_task.cancel()
    if topology_task is not None:
        topology_task.cancel()
    for t in (decay_task, topology_task):
        if t is not None:
            try:
                await t
            except asyncio.CancelledError:
                pass
    if decay_leader:
        _release_leader_lock("decay")
    if topology_leader:
        _release_leader_lock("topology")

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
app.include_router(graph_router)
