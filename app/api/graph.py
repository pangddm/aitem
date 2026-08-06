"""图拓扑查询接口：把当前用户沉淀的 K8s 关系以节点+边形式返回，供前端关系图渲染。"""
from fastapi import APIRouter, Query
from app.db.neo4j import neo4j
from app.core.config import TARGET_HOST, TARGET_PORT, TARGET_USERNAME, TARGET_PASSWORD
from app.tools.ssh_client import execute_command
from app.memory.graph.indexer import ClusterTopologyIndexer, get_topology_interval, set_topology_interval
from app.memory.repository.graph_repository import GraphRepository

router = APIRouter(prefix="/graph", tags=["graph"])



@router.get("/settings")
async def get_settings(user_id: str = Query(...)):
    """返回某账号的定时重建间隔（秒）"""
    return {"interval_seconds": get_topology_interval(user_id)}


@router.post("/settings")
async def update_settings(user_id: str = Query(...), interval_seconds: int = Query(..., ge=60, le=3600)):
    """设置某账号的定时重建间隔（秒，60~3600）"""
    sec = set_topology_interval(interval_seconds, user_id)
    return {"interval_seconds": sec}


@router.post("/rebuild")
async def rebuild_topology(user_id: str = Query(...), host: str = Query(None),
                           port: int = Query(None), username: str = Query(None),
                           password: str = Query(None)):
    """按需全量重建：从实际集群用 kubectl -o json 拉取并重建 Neo4j 拓扑"""
    hp = host or TARGET_HOST
    pp = port or TARGET_PORT
    up = username or TARGET_USERNAME
    pw = password or TARGET_PASSWORD
    driver = neo4j.get_driver()
    repo = GraphRepository(driver=driver)
    indexer = ClusterTopologyIndexer(driver=driver)
    stats = await indexer.rebuild(user_id, execute_command, hp, pp, up, pw, repo)
    return {"ok": True, **stats}

# 精简拓扑：Namespace -> （Service / 工作负载）-> Pod（ReplicaSet、Endpoints 折叠）
WORKLOADS = ("Deployment", "StatefulSet", "DaemonSet", "Job")
_LABEL_OR = " OR ".join(f"n:{l}" for l in ("Namespace", "Service") + WORKLOADS + ("Pod",))


@router.get("/topology")
async def get_topology(user_id: str = Query(...)):
    """返回当前账号的精简 K8s 拓扑：Namespace -> （Service/Deployment 等工作负载）-> Pod，折叠 ReplicaSet 与 Endpoints"""
    driver = neo4j.get_driver()
    async with driver.session() as s:
        nr = await s.run(
            f"""
            MATCH (n)
            WHERE ({_LABEL_OR}) AND n.owner = $uid
            RETURN labels(n)[0] AS t, n.name AS name
            """,
            uid=user_id,
        )
        node_rows = [dict(x) async for x in nr]

        # 边：Service/工作负载 属于 Namespace；Pod 经 Endpoints 折叠对接 Service、经 ReplicaSet 折叠归到工作负载
        er = await s.run(
            """
            MATCH (s:Service {owner:$uid})-[:BELONGS_TO]->(ns:Namespace)
            RETURN 'Service' AS at, s.name AS an, 'BELONGS_TO' AS rel, 'Namespace' AS bt, ns.name AS bn
            UNION
            MATCH (w)-[:BELONGS_TO]->(ns:Namespace)
            WHERE w.owner = $uid AND (w:Deployment OR w:StatefulSet OR w:DaemonSet OR w:Job)
            RETURN labels(w)[0] AS at, w.name AS an, 'BELONGS_TO' AS rel, 'Namespace' AS bt, ns.name AS bn
            UNION
            MATCH (p:Pod {owner:$uid})-[:BACKS]->(:Endpoints {owner:$uid})-[:SELECTS]->(svc:Service {owner:$uid})
            RETURN 'Pod' AS at, p.name AS an, 'BACKS' AS rel, 'Service' AS bt, svc.name AS bn
            UNION
            MATCH (p:Pod {owner:$uid})-[:BELONGS_TO]->(:ReplicaSet {owner:$uid})-[:BELONGS_TO]->(d:Deployment {owner:$uid})
            RETURN 'Pod' AS at, p.name AS an, 'BELONGS_TO' AS rel, 'Deployment' AS bt, d.name AS bn
            UNION
            MATCH (p:Pod {owner:$uid})-[:BELONGS_TO]->(w)
            WHERE w.owner = $uid AND (w:StatefulSet OR w:DaemonSet OR w:Job)
            RETURN 'Pod' AS at, p.name AS an, 'BELONGS_TO' AS rel, labels(w)[0] AS bt, w.name AS bn
            """,
            uid=user_id,
        )
        edge_rows = [dict(x) async for x in er]

    nodes = [{"id": f"{r['t']}|{r['name']}", "name": r["name"], "type": r["t"]} for r in node_rows]
    node_ids = {n["id"] for n in nodes}
    links = [
        {"source": f"{e['at']}|{e['an']}", "target": f"{e['bt']}|{e['bn']}", "rel": e["rel"]}
        for e in edge_rows if (f"{e['at']}|{e['an']}" in node_ids and f"{e['bt']}|{e['bn']}" in node_ids)
    ]
    return {"nodes": nodes, "links": links}
