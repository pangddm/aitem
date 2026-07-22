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

    # 3. 运行多 Agent 工作流
    workflow = AgentWorkflow()
    result = await workflow.run(
        user_id=user_id,
        user_message=user_message,
        memories=memories,
        knowledge_context=knowledge_context,
    )

    return result