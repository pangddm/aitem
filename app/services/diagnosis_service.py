from app.llm.agent import run_agent
from ..tools.tool_registry import execute_tool

async def chat_with_agent(message: str):

    # 第一次调用模型
    response = await run_agent(message)
    return response