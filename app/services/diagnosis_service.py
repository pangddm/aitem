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


    # ======================
    # 3. 保存Memory
    # ======================

    try:

    #     await memory_service.process(

    #         owner=user_id,

    #         messages=[

    #             {
    #                 "role":"user",
    #                 "content":user_message
    #             },

    #             {
    #                 "role":"assistant",
    #                 "content":response
    #             }

    #         ]

    #     )
        result = await service.process(

            owner=user_id,

            messages=[
                {
                    "role":"user",
                    "content":user_message
                },
                {
                    "role":"assistant",
                    "content":response
                }
            ]

        )

        print("Memory Process Result:", result)

    except Exception as e:

        print(
            f"Memory update error: {e}"
        )


    return response