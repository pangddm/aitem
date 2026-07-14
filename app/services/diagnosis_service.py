import traceback

from app.llm.agent import run_agent

from app.memory.container import memory_container


memory_service = None


async def get_memory_service():

    global memory_service

    if memory_service is None:

        memory_service = (
            memory_container.create_service()
        )

    return memory_service



async def chat_with_agent(
    user_id: str,
    user_message: str
):


    # ======================
    # 1. 查询长期Memory
    # ======================

    try:

        service = await get_memory_service()


        memories = await service.search(
            owner=user_id,
            query=user_message
        )


    except Exception as e:


        traceback.print_exc()

        memories = []



    # ======================
    # 2. Agent
    # ======================

    response = await run_agent(

        user_id=user_id,

        user_message=user_message,

        memories=memories

    )


    # 长期记忆已在 Agent 侧通过短期记忆桥接自动处理
    return response