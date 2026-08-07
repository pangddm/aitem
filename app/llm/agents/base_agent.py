"""
多 Agent 基类
所有子 Agent 继承此类，共享 LLM client 和通用方法
支持 DeepSeek reasoning_content（思考链）+ 流式推送 + 模型自动切换
"""

import json
import traceback
import asyncio

from app.llm.client import (
    get_client,
    get_current_model_name,
    get_current_model_display,
    switch_to_next_model,
    get_model_status,
)

# 可重试的连接错误关键词
RETRYABLE_ERRORS = (
    "peer closed connection",
    "incomplete chunked read",
    "Connection reset",
    "ConnectionError",
    "RemoteDisconnected",
    "ReadTimeout",
    "ConnectTimeout",
    "ServerDisconnectedError",
    "InternalServerError",
    "ServiceUnavailable",
    "RateLimitError",
    "APIConnectionError",
    "APITimeoutError",
    "TimeoutError",
    "timeout",
    "TimedOut",
)

MAX_RETRIES = 2  # 最多重试 2 次（含模型切换）


def _is_retryable(error: Exception) -> bool:
    """判断错误是否可重试"""
    error_str = str(error)
    for keyword in RETRYABLE_ERRORS:
        if keyword.lower() in error_str.lower():
            return True
    # 也检查异常类名
    error_type = type(error).__name__
    for keyword in RETRYABLE_ERRORS:
        if keyword.lower() in error_type.lower():
            return True
    return False


class BaseAgent:
    """Agent 基类"""

    def __init__(self, name: str = "base", model: str = None):
        self.name = name
        self.model = model or get_current_model_name()

    async def _call_with_retry(self, call_fn, error_prefix: str = "LLM 调用"):
        """
        带重试和模型切换的 LLM 调用包装器
        call_fn: 异步函数，接受 model 参数
        """
        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                return await call_fn()
            except Exception as e:
                last_error = e
                error_str = str(e)
                print(f"[{self.name}] {error_prefix}失败 (尝试 {attempt + 1}/{MAX_RETRIES + 1}): {error_str[:200]}")

                if not _is_retryable(e):
                    # 不可重试的错误（如参数错误），直接抛出
                    raise

                if attempt < MAX_RETRIES:
                    # 尝试切换模型
                    switched = await switch_to_next_model()
                    if switched:
                        print(f"[{self.name}] 已切换模型，重试中...")
                        await asyncio.sleep(0.5)  # 短暂等待
                    else:
                        print(f"[{self.name}] 所有模型都已失败")
                        break

        raise last_error

    async def think(self, system_prompt: str, user_message: str) -> str:
        """调用 LLM 进行思考，返回纯文本"""
        async def _call():
            c = get_client()
            response = await c.chat.completions.create(
                model=get_current_model_name(),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                timeout=60.0,
            )
            return response.choices[0].message.content.strip()

        try:
            return await self._call_with_retry(_call, "LLM 调用")
        except Exception as e:
            print(f"[{self.name}] LLM 调用最终失败: {e}")
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
        async def _call():
            c = get_client()
            response = await c.chat.completions.create(
                model=get_current_model_name(),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=8192,
                timeout=120.0,
            )
            msg = response.choices[0].message
            reasoning = getattr(msg, "reasoning_content", "") or ""
            content = msg.content or ""
            if not content and not reasoning:
                print(f"[{self.name}] ⚠️ LLM 返回空内容！finish_reason={response.choices[0].finish_reason}, model={get_current_model_name()}")
            elif not content:
                print(f"[{self.name}] ⚠️ LLM 返回空 content（仅有 reasoning），finish_reason={response.choices[0].finish_reason}")
            return {"reasoning": reasoning, "content": content}

        try:
            return await self._call_with_retry(_call, "LLM 调用")
        except Exception as e:
            print(f"[{self.name}] LLM 调用最终失败: {e}")
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

        data, ok = self._parse_json_response(raw)
        if ok:
            return {"reasoning": reasoning, "data": data, "parse_failed": False}

        # JSON 解析失败：追加纠错提示重试一次，要求只输出严格 JSON
        print(f"[{self.name}] JSON 解析失败，追加纠错提示重试...")
        retry_result = await self.think_with_reasoning(
            system_prompt,
            user_message + "\n\n⚠️ 上次输出不是有效 JSON。请重新回答，并且【只】输出严格的 JSON 对象，不要包含任何解释、注释或 Markdown 代码块。",
        )
        raw2 = retry_result.get("content", "") or ""
        reasoning2 = retry_result.get("reasoning", "") or reasoning
        data2, ok2 = self._parse_json_response(raw2)

        if not ok2:
            # 仍失败：标记 parse_failed，让调用方（如 Orchestrator）降级为
            # “按知识库/文档内容正常回答”，而不是中途中断或输出残缺内容
            print(f"[{self.name}] JSON 无法修复，原始内容: {(raw or raw2)[:300]}")
            return {
                "reasoning": reasoning2,
                "data": {},
                "parse_failed": True,
                "raw": (raw or raw2)[:2000],
            }

        print(f"[{self.name}] JSON 重试解析成功")
        return {"reasoning": reasoning2, "data": data2, "parse_failed": False}

    def _parse_json_response(self, raw: str):
        """尝试把 LLM 返回内容解析为 JSON（支持 Markdown 代码块与常见截断）。返回 (data, ok)。"""
        if not raw or not raw.strip():
            return ({}, False)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)
        try:
            return (json.loads(cleaned), True)
        except json.JSONDecodeError:
            # 尝试修复常见的 JSON 截断问题
            print(f"[{self.name}] JSON 解析失败，尝试修复...")
            fixed = cleaned.strip()
            open_braces = fixed.count("{") - fixed.count("}")
            open_brackets = fixed.count("[") - fixed.count("]")
            if open_braces > 0 or open_brackets > 0:
                fixed = fixed.rstrip().rstrip(",")
                fixed += "}" * open_braces + "]" * open_brackets
                try:
                    return (json.loads(fixed), True)
                except json.JSONDecodeError:
                    print(f"[{self.name}] JSON 修复失败，原始内容: {raw[:300]}")
                    return ({}, False)
            else:
                print(f"[{self.name}] JSON 无未闭合括号，原始内容: {raw[:300]}")
                return ({}, False)

    async def think_stream(self, system_prompt: str, user_message: str):
        """
        流式调用 LLM，yield 字典事件
        支持自动重试和模型切换

        yield 格式:
            {"type": "reasoning", "content": "..."}   # 思考链
            {"type": "content", "content": "..."}      # 正文
            {"type": "model_switched", "model": "...", "display": "..."}  # 模型切换通知
            {"type": "error", "content": "..."}        # 错误信息
        """
        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                c = get_client()
                stream = await c.chat.completions.create(
                    model=get_current_model_name(),
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    stream=True,
                    timeout=120.0,  # 增加超时时间
                )
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    # 收集思考链
                    rc = getattr(delta, "reasoning_content", "") or ""
                    if rc:
                        yield {"type": "reasoning", "content": rc}

                    # 收集正文
                    ct = delta.content or ""
                    if ct:
                        yield {"type": "content", "content": ct}

                # 流式成功完成，退出重试循环
                return

            except Exception as e:
                last_error = e
                error_str = str(e)
                print(f"[{self.name}] 流式调用失败 (尝试 {attempt + 1}/{MAX_RETRIES + 1}): {error_str[:200]}")

                if not _is_retryable(e):
                    # 不可重试的错误，直接报错
                    yield {"type": "error", "content": f"生成回复时出错: {e}"}
                    return

                if attempt < MAX_RETRIES:
                    # 递增等待时间：0.5s, 1.0s, 1.5s...
                    wait_time = 0.5 * (attempt + 1)
                    print(f"[{self.name}] 等待 {wait_time}s 后重试...")
                    await asyncio.sleep(wait_time)

                    switched = await switch_to_next_model()
                    if switched:
                        display = get_current_model_display()
                        yield {"type": "model_switched", "model": get_current_model_name(), "display": display}
                        print(f"[{self.name}] 已切换到 {display}，准备重试...")
                        await asyncio.sleep(0.5)  # 切换后额外等待
                    else:
                        print(f"[{self.name}] 所有模型都已失败，无法切换")
                        break

        # 所有重试都失败了
        error_msg = f"生成回复时出错（已重试 {MAX_RETRIES} 次）: {last_error}"
        print(f"[{self.name}] 流式调用最终失败: {last_error}")
        traceback.print_exc()
        yield {"type": "error", "content": error_msg}
