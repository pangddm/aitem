"""快速测试 DeepSeek API 是否可用"""
import asyncio
from app.llm.client import get_client

async def test():
    print("正在调用 DeepSeek API...")
    try:
        response = await asyncio.wait_for(
            get_client().chat.completions.create(
                model="deepseek-v4-flash",
                messages=[
                    {"role": "user", "content": "你好，请说一个词"},
                ],
            ),
            timeout=10.0  # 10 秒超时
        )
        print(f"API 响应: {response.choices[0].message.content}")
    except asyncio.TimeoutError:
        print("API 调用超时（10秒）")
    except Exception as e:
        print(f"API 调用失败: {type(e).__name__}: {e}")

asyncio.run(test())
