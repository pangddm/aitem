import traceback

from app.llm.agents import AgentWorkflow
from app.memory.container import memory_container
from app.knowledge.factory import knowledge_factory


memory_service = None


async def get_memory_service():
    global memory_service
    if memory_service is None:
        memory_service = memory_container.create_service()
    return memory_service


async def _retrieve_knowledge_context(user_id: str, query: str) -> str:
    """检索用户知识库上下文"""
    try:
        kbs = await knowledge_factory.kb_repository.list_by_owner(user_id)
        if kbs:
            service = knowledge_factory.service
            context_parts = []
            for kb in kbs:
                ctx = await service.retrieve_context(
                    kb_id=kb.id,
                    query=query,
                )
                if ctx:
                    context_parts.append(ctx)
            return "\n".join(context_parts) if context_parts else ""
        return ""
    except Exception as e:
        print(f"[RAG] 知识库检索失败: {type(e).__name__}: {e}")
        traceback.print_exc()
        return ""


async def _retrieve_graph_context(user_id: str, query: str) -> str:
    """检索 Neo4j 图上的拓扑/审计，作为参考提示注入（须以 kubectl 实测为准）"""
    try:
        from app.memory.repository.graph_retriever import GraphTopologyRetriever
        from app.db.neo4j import neo4j
        retriever = GraphTopologyRetriever(driver=neo4j.get_driver())
        return await retriever.retrieve_for_query(user_id, query)
    except Exception as e:
        print(f"[Graph] 图拓扑检索失败: {type(e).__name__}: {e}")
        return ""


async def chat_with_agent(
    user_id: str,
    user_message: str
):
    # 1. 查询长期 Memory
    try:
        service = await get_memory_service()
        memories = await service.search(
            owner=user_id,
            query=user_message
        )
    except Exception as e:
        traceback.print_exc()
        memories = []

    # 2. 检索知识库上下文
    knowledge_context = await _retrieve_knowledge_context(user_id, user_message)

    # 2.5 注入图拓扑/审计参考（方案A：图仅作提示，事实以 kubectl 实测为准）
    graph_context = await _retrieve_graph_context(user_id, user_message)
    if graph_context:
        knowledge_context = "【集群拓扑图参考（缓存提示，须用 kubectl 复核）】\n" + graph_context + "\n\n" + knowledge_context
        print(f"[Graph] 注入拓扑上下文 {len(graph_context)} 字符")

    # 3. 运行多 Agent 工作流
    workflow = AgentWorkflow()
    result = await workflow.run(
        user_id=user_id,
        user_message=user_message,
        memories=memories,
        knowledge_context=knowledge_context,
    )

    return result