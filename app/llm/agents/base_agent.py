"""
多 Agent 基类
所有子 Agent 继承此类，共享 LLM client 和通用方法
支持 DeepSeek reasoning_content（思考链）
"""

import json
import traceback

from app.llm.client import client


class BaseAgent:
    """Agent 基类"""

    def __init__(self, name: str = "base", model: str = "deepseek-v4-flash"):
        self.name = name
        self.model = model

    async def think(self, system_prompt: str, user_message: str) -> str:
        """调用 LLM 进行思考，返回纯文本"""
        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[{self.name}] LLM 调用失败: {e}")
            traceback.print_exc()
            return ""

    async def think_with_reasoning(self, system_prompt: str, user_message: str) -> dict:
        """
        调用 LLM，返回包含 reasoning 和 content 的字典
        
        返回:
            {
                "reasoning": str,   # 思考链（DeepSeek reasoning_content）
                "content": str,     # 最终内容
            }
        """
        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
            msg = response.choices[0].message
            reasoning = getattr(msg, "reasoning_content", "") or ""
            content = msg.content or ""
            return {"reasoning": reasoning, "content": content}
        except Exception as e:
            print(f"[{self.name}] LLM 调用失败: {e}")
            traceback.print_exc()
            return {"reasoning": "", "content": ""}

    async def think_json_with_reasoning(self, system_prompt: str, user_message: str) -> dict:
        """
        调用 LLM 并解析 JSON 响应，同时返回思考链
        
        返回:
            {
                "reasoning": str,   # 思考链
                "data": dict,       # 解析后的 JSON
            }
        """
        result = await self.think_with_reasoning(system_prompt, user_message)
        raw = result.get("content", "")
        reasoning = result.get("reasoning", "")

        if not raw:
            return {"reasoning": reasoning, "data": {}}

        # 清理 markdown 代码块
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            print(f"[{self.name}] JSON 解析失败，原始内容: {raw[:200]}")
            data = {}

        return {"reasoning": reasoning, "data": data}

    async def think_stream(self, system_prompt: str, user_message: str):
        """
        流式调用 LLM，yield 字典事件
        
        yield 格式:
            {"type": "reasoning", "content": "..."}   # 思考链
            {"type": "content", "content": "..."}      # 正文
        """
        try:
            stream = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta

                # 收集思考链
                rc = getattr(delta, "reasoning_content", "") or ""
                if rc:
                    yield {"type": "reasoning", "content": rc}

                # 收集正文
                ct = delta.content or ""
                if ct:
                    yield {"type": "content", "content": ct}

        except Exception as e:
            print(f"[{self.name}] 流式调用失败: {e}")
            traceback.print_exc()