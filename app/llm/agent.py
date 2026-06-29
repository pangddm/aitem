from app.llm.client import client
from app.core.prompts import SYSTEM_PROMPT
from app.core.tools import TOOLS
import json
from app.tools.tool_registry import execute_tool
from app.schemas.check import is_safe_command
async def run_agent(user_message: str):

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": user_message
        }
    ]
    MAX_ROUNDS = 3

    round_count = 0

    while round_count < MAX_ROUNDS:

        round_count += 1

        response = await client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=messages,
            tools=TOOLS
        )

        assistant_message = response.choices[0].message

        if not assistant_message.tool_calls:
            return assistant_message.content

        messages.append(assistant_message)

        # 本轮可能执行多个工具
        for tool_call in assistant_message.tool_calls:

            try:
                tool_result = await execute_tool(tool_call)

            except Exception as e:
                tool_result = f"工具执行失败: {e}"

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(tool_result)
            })

    return f"Agent 执行超过 {MAX_ROUNDS} 轮，任务终止。"