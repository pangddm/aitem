from app.llm.client import client
from app.prompt.sys import SYSTEM_PROMPT
from app.prompt.tools import TOOLS
from app.knowledge.factory import knowledge_factory
import json
import traceback
from app.tools.tool_registry import execute_tool
from app.schemas.check import is_safe_command
from app.memory.short_term import SessionMemory, r
from app.memory.container import memory_container
from app.memory.short_term_bridge import ShortTermMemoryBridge
from app.memory.repository.graph_repository import GraphRepository
from app.db.neo4j import neo4j
MAX_ROUNDS = 6  # 防止无限 LLM ↔ tool 循环


def _extract_entities_from_command(command: str):
    if not command:
        return []

    entities = []
    parts = command.split()
    for index, part in enumerate(parts):
        if part in {"pod", "pods", "deployment", "deploy", "namespace", "ns"}:
            if index + 1 < len(parts):
                entities.append(f"{part.title()}/{parts[index + 1]}")
        elif part.startswith("kubectl"):
            continue
        elif part.startswith("nginx") or part.startswith("coredns"):
            entities.append(part)

    return entities


async def run_agent(
    user_id: str,
    user_message: str,
    memories=None
):
    """
    返回:
        {
            "answer": str,        # 最终回答
            "reasoning": str,     # 思考链（DeepSeek reasoning_content）
            "tool_calls": [...]   # 工具调用记录
        }
    """

    memory = SessionMemory()

    # 1. 加载历史会话
    history = memory.load(user_id)

    # 2. 拼接 messages
    memory_context = ""
    knowledge_context = ""

    try:

        # 查找用户的所有知识库，逐个检索并合并结果
        kbs = await knowledge_factory.kb_repository.list_by_owner(user_id)
        if kbs:
            service = knowledge_factory.service
            context_parts = []
            for kb in kbs:
                ctx = await service.retrieve_context(
                    kb_id=kb.id,
                    query=user_message,
                )
                if ctx:
                    context_parts.append(ctx)
            knowledge_context = "\n".join(context_parts) if context_parts else ""
        else:
            knowledge_context = ""

    except Exception as e:
        import traceback as _tb
        print(f"[RAG] 知识库检索失败: {type(e).__name__}: {e}")
        _tb.print_exc()

    if memories:

        memory_context = "\n\n".join(
            [
                f"""
                    Memory:
                    类型: {m.type.value}
                    内容: {m.content}
                    摘要: {m.summary}
                    实体: {m.entities}
                    """
                    for m in memories
                ]
            )


    system_prompt = SYSTEM_PROMPT

    if knowledge_context:

        system_prompt += f"""

    ======================
    以下是历史知识库案例

    {knowledge_context}

    要求：

    1、仅作为参考

    2、优先相信实时 Tool

    3、如果历史案例适用，可以直接复用解决方案

    4、不要直接复制历史回答，而是结合当前 Tool 输出分析

    ======================

    """


    if memory_context:

        system_prompt += f"""

    以下是历史长期记忆，仅作为辅助信息：

    {memory_context}


    使用规则：

    1. 不要盲目信任Memory
    2. 如果Memory和实时Kubernetes状态冲突，以实时Tool结果为准
    3. Memory用于提供历史经验和排查方向

    """


    messages = [
        {
            "role":"system",
            "content":system_prompt
        },
        *history,
        {
            "role":"user",
            "content":user_message
        }
    ]

    round_count = 0
    reasoning_parts = []   # 收集所有轮的思考链
    tool_call_log = []     # 工具调用记录

    while round_count < MAX_ROUNDS:

        round_count += 1

        response = await client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=messages,
            tools=TOOLS
        )

        assistant_message = response.choices[0].message

        # 收集思考链
        rc = getattr(assistant_message, "reasoning_content", "")
        if rc:
            reasoning_parts.append(rc)

        # =========================
        # 最终回答
        # =========================
        if not assistant_message.tool_calls:

            final_answer = assistant_message.content

            # 保存本轮对话到 Redis
            history.append({
                "role": "user",
                "content": user_message
            })

            history.append({
                "role": "assistant",
                "content": final_answer
            })

            memory.save(user_id, history)
            memory.append_conversation(user_id, "user", user_message)
            memory.append_conversation(user_id, "assistant", final_answer)

            try:
                service = memory_container.create_service()
                bridge = ShortTermMemoryBridge(
                    redis_client=r,
                    memory_service=service,
                )
                await bridge.process_conversation(
                    owner=user_id,
                    conversation_id=user_id,
                )
            except Exception as e:
                print(f"Short-term memory bridge error: {e}")

            return {
                "answer": final_answer,
                "reasoning": "\n\n".join(reasoning_parts) if reasoning_parts else "",
                "tool_calls": tool_call_log,
            }

        # =========================
        # 保存 assistant tool call
        # =========================
        messages.append(assistant_message)

        # =========================
        # 执行工具
        # =========================
        for tool_call in assistant_message.tool_calls:

            tool_name = tool_call.function.name

            arguments = json.loads(
                tool_call.function.arguments
            )

            command_value = arguments.get(
                "command",
                ""
            )

            print(f"调用工具: {tool_name}")
            print(f"工具参数: {command_value}")

            try:

                if is_safe_command(command_value):

                    tool_result = await execute_tool(
                        tool_call
                    )

                else:

                    tool_result = (
                        f"命令不安全，已被拒绝执行: "
                        f"{command_value}"
                    )

            except Exception as e:

                tool_result = (
                    f"工具执行失败: {str(e)}"
                )

            # 记录工具调用
            tool_call_log.append({
                "tool": tool_name,
                "command": command_value,
                "result": str(tool_result)[:500],
            })

            # 协议要求
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(tool_result)
            })

            try:
                graph_repo = GraphRepository(driver=neo4j.get_driver())
                entities = _extract_entities_from_command(command_value)
                if entities:
                    await graph_repo.upsert_tool_entities(
                        owner=user_id,
                        command=command_value,
                        tool_result=str(tool_result),
                        entities=entities,
                    )
            except Exception as e:
                print(f"Tool graph sync error: {e}")

    # =========================
    # 超过最大轮次
    # =========================

    final_answer = (
        f"Agent 超过最大轮数 "
        f"{MAX_ROUNDS}，已终止执行。"
    )

    try:
        service = memory_container.create_service()
        bridge = ShortTermMemoryBridge(
            redis_client=r,
            memory_service=service,
        )
        await bridge.process_conversation(
            owner=user_id,
            conversation_id=user_id,
        )
    except Exception as e:
        print(f"Short-term memory bridge error: {e}")

    return {
        "answer": final_answer,
        "reasoning": "\n\n".join(reasoning_parts) if reasoning_parts else "",
        "tool_calls": tool_call_log,
    }


async def run_agent_stream(
    user_id: str,
    user_message: str,
    memories=None
):
    """流式版 Agent：逐 token yield 事件，供 SSE 推送。
    
    yield 事件格式:
        {"type":"reasoning", "content":"..."}
        {"type":"answer_chunk", "content":"..."}
        {"type":"tool_call", "tool":"...", "command":"..."}
        {"type":"tool_result", "tool":"...", "result":"..."}
        {"type":"done"}
    """

    # ── 初始化（同 run_agent）──
    memory = SessionMemory()
    history = memory.load(user_id)
    knowledge_context = ""

    try:
        kbs = await knowledge_factory.kb_repository.list_by_owner(user_id)
        if kbs:
            service = knowledge_factory.service
            parts = []
            for kb in kbs:
                ctx = await service.retrieve_context(kb_id=kb.id, query=user_message)
                if ctx:
                    parts.append(ctx)
            knowledge_context = "\n".join(parts) if parts else ""
    except Exception:
        knowledge_context = ""

    memory_context = ""
    if memories:
        memory_context = "\n\n".join(
            f"Memory:\n类型: {m.type.value}\n内容: {m.content}\n摘要: {m.summary}\n实体: {m.entities}"
            for m in memories
        )

    system_prompt = SYSTEM_PROMPT
    if knowledge_context:
        system_prompt += f"\n\n历史知识库案例:\n{knowledge_context}"
    if memory_context:
        system_prompt += f"\n\n历史长期记忆:\n{memory_context}"

    messages = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": user_message},
    ]

    round_count = 0
    all_reasoning = []
    all_tool_calls = []
    all_answer_chunks = []  # 收集完整答案

    while round_count < MAX_ROUNDS:
        round_count += 1

        try:
            stream = await client.chat.completions.create(
                model="deepseek-v4-flash",
                messages=messages,
                tools=TOOLS,
                stream=True,
            )
        except Exception as e:
            print(f"[Agent Stream] API 调用失败: {e}")
            traceback.print_exc()
            yield {"type": "error", "content": f"LLM 调用失败: {e}"}
            return

        tool_call_buf: dict[int, dict] = {}

        try:
            async for chunk in stream:
                delta = chunk.choices[0].delta

                rc = getattr(delta, "reasoning_content", "") or ""
                if rc:
                    all_reasoning.append(rc)
                    yield {"type": "reasoning", "content": rc}

                ct = delta.content or ""
                if ct:
                    all_answer_chunks.append(ct)
                    yield {"type": "answer_chunk", "content": ct}

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_call_buf:
                            tool_call_buf[idx] = {
                                "id": tc.id or "", "name": "", "arguments": "",
                            }
                        if tc.function:
                            if tc.function.name:
                                tool_call_buf[idx]["name"] += tc.function.name
                            if tc.function.arguments:
                                tool_call_buf[idx]["arguments"] += tc.function.arguments
        except Exception as e:
            print(f"[Agent Stream] chunk 读取失败: {e}")
            traceback.print_exc()
            yield {"type": "error", "content": str(e)}
            return

        if not tool_call_buf:
            full_answer = "".join(all_answer_chunks)
            history.append({"role": "user", "content": user_message})
            history.append({"role": "assistant", "content": full_answer})
            memory.save(user_id, history)
            try:
                service = memory_container.create_service()
                bridge = ShortTermMemoryBridge(redis_client=r, memory_service=service)
                await bridge.process_conversation(owner=user_id, conversation_id=user_id)
            except Exception:
                pass
            yield {"type": "done"}
            return

        # 有工具调用 → 构建 assistant message + 执行工具
        tc_list = []
        for idx in sorted(tool_call_buf.keys()):
            tc = tool_call_buf[idx]
            tc_list.append({
                "id": tc["id"],
                "type": "function",
                "function": {"name": tc["name"], "arguments": tc["arguments"]},
            })

        # 构建 assistant 消息
        from openai.types.chat import ChatCompletionMessage, ChatCompletionMessageToolCall
        from openai.types.chat.chat_completion_message_tool_call import Function as TCFunc

        tool_calls_obj = [
            ChatCompletionMessageToolCall(
                id=tc["id"],
                type="function",
                function=TCFunc(
                    name=tc["function"]["name"],
                    arguments=tc["function"]["arguments"],
                ),
            )
            for tc in tc_list
        ]
        assistant_msg = ChatCompletionMessage(
            role="assistant", content=None, tool_calls=tool_calls_obj
        )
        messages.append(assistant_msg)

        # 执行工具
        for tc in tc_list:
            tool_name = tc["function"]["name"]
            args = json.loads(tc["function"]["arguments"])
            cmd = args.get("command", "")
            yield {"type": "tool_call", "tool": tool_name, "command": cmd}

            try:
                if is_safe_command(cmd):
                    from types import SimpleNamespace
                    fake_tc = SimpleNamespace(
                        id=tc["id"],
                        function=SimpleNamespace(
                            name=tc["function"]["name"],
                            arguments=tc["function"]["arguments"],
                        ),
                    )
                    result = await execute_tool(fake_tc)
                else:
                    result = f"命令不安全: {cmd}"
            except Exception as e:
                traceback.print_exc()
                result = f"工具执行失败: {e}"

            yield {"type": "tool_result", "tool": tool_name, "result": str(result)[:500]}
            all_tool_calls.append({"tool": tool_name, "command": cmd, "result": str(result)[:500]})
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": str(result),
            })

    yield {"type": "done"}