from app.llm.client import client
from app.core.prompts import SYSTEM_PROMPT

async def run_agent(user_message: str):

    response = await client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user_message
            }
        ]
    )

    return response