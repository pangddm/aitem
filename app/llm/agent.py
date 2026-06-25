from app.llm.client import client
from app.core.prompts import SYSTEM_PROMPT
from app.core.tools import TOOLS
from app.tools.tool_registry import execute_tool
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
    while True:

        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=TOOLS
        )

        assistant_message = response.choices[0].message

        # # 模型已经给出了最终答案
        if not assistant_message.tool_calls:
            return assistant_message.content

        # 保存模型的tool call
        messages.append(assistant_message)

        # 执行工具
        for tool_call in assistant_message.tool_calls:

            tool_result = await execute_tool(tool_call)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(tool_result)
            })