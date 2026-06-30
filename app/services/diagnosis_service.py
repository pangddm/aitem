from app.llm.agent import run_agent
from ..tools.tool_registry import execute_tool

async def chat_with_agent(user_id: str, user_message: str):

    # 第一次调用模型
    response = await run_agent(user_id, user_message)
    return response