import json

from app.schemas.check import is_safe_command
from app.tools.tool_registry import execute_tool


class ToolExecutor:

    async def execute(
        self,
        tool_call,
    ):

        tool_name = tool_call.function.name

        arguments = json.loads(
            tool_call.function.arguments
        )

        command = arguments.get(
            "command",
            "",
        )

        if not is_safe_command(
            command,
        ):

            return {

                "tool": tool_name,

                "command": command,

                "result": "Unsafe command.",

            }

        result = await execute_tool(
            tool_call
        )

        return {

            "tool": tool_name,

            "command": command,

            "result": str(result),

        }