import asyncio
import json
from functools import partial

from app.tools.ssh_client import execute_command

TOOL_MAP = {
    "execute_command": execute_command,
}


async def execute_tool(tool_call):

    tool_name = tool_call.function.name

    # 把 JSON 字符串转成字典
    arguments = json.loads(tool_call.function.arguments)

    # 获取对应函数
    tool_func = TOOL_MAP.get(tool_name)

    if tool_func is None:
        raise ValueError(f"未知工具: {tool_name}")

    # 在线程池中执行同步阻塞函数，避免阻塞事件循环
    # run_in_executor 只接受 fn(*args) 位置参数，用 partial 绑定关键字参数
    bound_func = partial(tool_func, **arguments)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, bound_func)

    return result