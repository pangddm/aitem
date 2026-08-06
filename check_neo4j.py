import asyncio
from neo4j import AsyncGraphDatabase
from app.core.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

USER_ID = "c687f3cc-3bff-4ed1-a291-d7aed3035d6b"

async def main():
    print(f"连接 {NEO4J_URI}  user={NEO4J_USER}")
    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        async with driver.session() as s:
            r = await s.run("MATCH (n) RETURN labels(n) AS label, count(*) AS c ORDER BY c DESC")
            print("\n== 各类节点数量 ==")
            async for rec in r:
                print(f"   {rec['label']}: {rec['c']}")

            r = await s.run("MATCH ()-[r]->() RETURN type(r) AS rel, count(*) AS c ORDER BY c DESC")
            print("\n== 各类关系数量 ==")
            async for rec in r:
                print(f"   {rec['rel']}: {rec['c']}")

            r = await s.run(
                "MATCH (u:User {id:$uid})-[:RELATED_TO]->(e) "
                "RETURN labels(e) AS lt, e.name AS name, e.last_action AS action, e.last_state AS state "
                "ORDER BY lt, name",
                uid=USER_ID,
            )
            print(f"\n== 用户 {USER_ID} 关联的资源实体 ==")
            rows = []
            async for rec in r:
                rows.append((rec['lt'], rec['name'], rec['action'], rec['state']))
            if not rows:
                print("   (空) 这个用户还没有资源实体写入")
            for lt, name, action, state in rows:
                print(f"   {lt} / {name}    action={action}  state={state}")

            r = await s.run(
                "MATCH (d:Deployment)-[:BELONGS_TO]->(n:Namespace) "
                "OPTIONAL MATCH (r:ReplicaSet)-[:BELONGS_TO]->(d) "
                "OPTIONAL MATCH (p:Pod)-[:BELONGS_TO]->(r) "
                "RETURN d.name AS dep, n.name AS ns, r.name AS rs, p.name AS pod "
                "ORDER BY dep"
            )
            print("\n== 拓扑: Namespace <- Deployment <- ReplicaSet <- Pod ==")
            rows = []
            async for rec in r:
                rows.append((rec['dep'], rec['ns'], rec['rs'], rec['pod']))
            if not rows:
                print("   (空)")
            for dep, ns, rs, pod in rows:
                print(f"   {ns} / {dep}  ->  {rs}  ->  {pod}")

            r = await s.run(
                "MATCH (c)-[:BELONGS_TO]->(n:Namespace) "
                "WHERE (c:StatefulSet OR c:DaemonSet OR c:Job) "
                "OPTIONAL MATCH (p:Pod)-[:BELONGS_TO]->(c) "
                "RETURN labels(c) AS lt, c.name AS cname, n.name AS ns, p.name AS pod "
                "ORDER BY lt, cname"
            )
            print("\n== 拓扑: Namespace <- StatefulSet/DaemonSet/Job <- Pod ==")
            rows = []
            async for rec in r:
                rows.append((rec['lt'], rec['cname'], rec['ns'], rec['pod']))
            if not rows:
                print("   (空)")
            for lt, cname, ns, pod in rows:
                print(f"   {ns} / {lt} / {cname}  ->  {pod}")

            r = await s.run(
                "MATCH (svc:Service)-[:BELONGS_TO]->(n:Namespace) "
                "OPTIONAL MATCH (ep:Endpoints)-[:SELECTS]->(svc) "
                "RETURN n.name AS ns, svc.name AS svc, ep.name AS ep ORDER BY svc"
            )
            print("\n== 拓扑: Namespace <- Service <- Endpoints ==")
            rows = []
            async for rec in r:
                rows.append((rec['ns'], rec['svc'], rec['ep']))
            if not rows:
                print("   (空)")
            for ns, svc, ep in rows:
                print(f"   {ns} / {svc}  ->  {ep}")

            r = await s.run(
                "MATCH (b)-[g:GRANTS]->(role) "
                "OPTIONAL MATCH (b)-[a:ASSIGNED_TO]->(subj) "
                "RETURN labels(b)[0] AS bt, b.name AS bn, labels(role)[0] AS rt, role.name AS rn, "
                "       labels(subj)[0] AS st, subj.name AS sn "
                "ORDER BY bt, bn"
            )
            print("\n== RBAC: Binding -> GRANTS -> Role ; Binding -> ASSIGNED_TO -> Subject ==")
            rows = []
            async for rec in r:
                rows.append((rec['bt'], rec['bn'], rec['rt'], rec['rn'], rec['st'], rec['sn']))
            if not rows:
                print("   (空)")
            for bt, bn, rt, rn, st, sn in rows:
                print(f"   {bt}/{bn} -GRANTS-> {rt}/{rn}  ;  {bt}/{bn} -ASSIGNED_TO-> {st}/{sn}")

    finally:
        await driver.close()
        print("\n连接已关闭")

asyncio.run(main())
