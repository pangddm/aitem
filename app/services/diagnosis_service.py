from app.llm.agent import run_agent

async def chat_with_agent(message: str):

    response = await run_agent(message)

    tool_calls = response.choices[0].message.tool_calls

    if tool_calls:
        ...
    
    return {
        "answer": response.choices[0].message.content
    }