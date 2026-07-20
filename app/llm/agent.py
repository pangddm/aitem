from app.llm.client import client
from app.prompt.sys import SYSTEM_PROMPT
from app.prompt.tools import TOOLS
from app.knowledge.factory import knowledge_factory
import json
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
        print(f"[RAG] 知识库检索失败: {e}")

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

    while round_count < MAX_ROUNDS:

        round_count += 1

        response = await client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=messages,
            tools=TOOLS
        )

        assistant_message = response.choices[0].message

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

            return final_answer

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
            print(f"工具响应: {assistant_message}")

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

    return final_answer