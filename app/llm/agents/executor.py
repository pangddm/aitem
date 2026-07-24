"""
Executor Agent — 执行者
职责：通过 SSH 执行经过校验的 kubectl 命令
"""

import json
from types import SimpleNamespace

from app.llm.agents.base_agent import BaseAgent
from app.tools.tool_registry import execute_tool


class Executor(BaseAgent):
    """执行者：执行经过校验的命令"""

    def __init__(self):
        super().__init__(name="executor")

    async def execute(self, command: str, host: str = None, port: int = None, username: str = None, password: str = None) -> dict:
        """
        执行命令，返回结果

        返回:
            {
                "command": str,    # 执行的命令
                "success": bool,   # 是否执行成功
                "result": str,     # 执行结果
                "error": str,      # 错误信息
            }
        """
        if not command:
            return {
                "command": "",
                "success": False,
                "result": "",
                "error": "命令为空",
            }

        # 构造 tool_call 对象（兼容 execute_tool 接口）
        fake_tool_call = SimpleNamespace(
            id=f"exec-{hash(command) % 10000}",
            function=SimpleNamespace(
                name="execute_command",
                arguments=json.dumps({"command": command}),
            ),
        )

        try:
            result = await execute_tool(fake_tool_call, host=host, port=port, username=username, password=password)
            return {
                "command": command,
                "success": True,
                "result": str(result),
                "error": "",
            }
        except Exception as e:
            return {
                "command": command,
                "success": False,
                "result": "",
                "error": str(e),
            }
