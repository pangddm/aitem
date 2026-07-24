import asyncio
import json
from functools import partial

from app.tools.ssh_client import execute_command

TOOL_MAP = {
    "execute_command": execute_command,
}


async def execute_tool(tool_call, host: str = None, port: int = None, username: str = None, password: str = None):

    tool_name = tool_call.function.name

    # 把 JSON 字符串转成字典
    arguments = json.loads(tool_call.function.arguments)

    # 获取对应函数
    tool_func = TOOL_MAP.get(tool_name)

    if tool_func is None:
        raise ValueError(f"未知工具: {tool_name}")

    # 在线程池中执行同步阻塞函数，避免阻塞事件循环
    # run_in_executor 只接受 fn(*args) 位置参数，用 partial 绑定关键字参数
    # 传递动态主机参数（仅对 execute_command 生效）
    extra_kwargs = {}
    if tool_name == "execute_command":
        if host is not None:
            extra_kwargs["host"] = host
        if port is not None:
            extra_kwargs["port"] = port
        if username is not None:
            extra_kwargs["username"] = username
        if password is not None:
            extra_kwargs["password"] = password

    bound_func = partial(tool_func, **arguments, **extra_kwargs)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, bound_func)

    return result