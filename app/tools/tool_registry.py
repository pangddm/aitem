import json

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

    # 执行工具
    result = tool_func(**arguments)

    return result