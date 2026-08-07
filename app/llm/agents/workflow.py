"""
Agent 工作流引擎
串联所有 Agent，完成从意图分析到结果报告的完整流程
支持并行执行、思考链推送、反馈循环（Observer → Validator 重试）
"""

import asyncio
import os
import re
import traceback

from app.llm.agents.orchestrator import Orchestrator
from app.llm.agents.risk_assessor import RiskAssessor
from app.llm.agents.validator import Validator
from app.llm.agents.executor import Executor
from app.llm.agents.observer import Observer
from app.llm.agents.reporter import Reporter
from app.llm.agents.command_rewriter import CommandRewriter
from app.core.config import (
    AUTO_EXEC_CONFIDENCE,
    MAX_RETRY_LOOPS,
    MAX_AGENT_ITERATIONS,
    LOOP_NO_PROGRESS_LIMIT,
)
from app.llm.client import get_current_model_display, get_model_status


class AgentWorkflow:
    """多 Agent 工作流引擎"""

    def __init__(self):
        self.orchestrator = Orchestrator()
        self.risk_assessor = RiskAssessor()
        self.validator = Validator()
        self.executor = Executor()
        self.observer = Observer()
        self.reporter = Reporter()
        self.command_rewriter = CommandRewriter()

    async def run(
        self,
        user_id: str,
        user_message: str,
        memories: list = None,
        knowledge_context: str = "",
    ) -> dict:
        """
        运行完整工作流（非流式），并行执行风险评估和命令生成
        """
        print(f"[Workflow] 用户 {user_id} 发起请求: {user_message}")

        all_reasoning = []

        # 1. Orchestrator — 意图分析
        orc_result = await self.orchestrator.analyze(user_message)
        task_plan = orc_result["task_plan"]
        if orc_result["reasoning"]:
            all_reasoning.append(f"[意图分析] {orc_result['reasoning']}")
        print(f"[Workflow] 任务计划: {task_plan}")

        # 如果不需要执行（理论知识等），直接报告
        if not task_plan.get("requires_execution"):
            rep_result = await self.reporter.report(
                task_plan, {}, {}, {}, {},
                memories=memories, knowledge_context=knowledge_context,
            )
            if rep_result.get("reasoning"):
                all_reasoning.append(f"[报告生成] {rep_result['reasoning']}")
            return {
                "answer": rep_result.get("answer", ""),
                "reasoning": "\n\n".join(all_reasoning),
                "task_plan": task_plan,
            }

        # 2. 并行执行：Risk Assessor + Validator 命令生成
        risk_task = self.risk_assessor.assess(task_plan)
        cmd_task = self.validator.generate_command(task_plan, memories=memories)

        risk_result, cmd_result = await asyncio.gather(risk_task, cmd_task)

        risk_assessment = risk_result["risk_assessment"]
        if risk_result["reasoning"]:
            all_reasoning.append(f"[风险评估] {risk_result['reasoning']}")

        if cmd_result["reasoning"]:
            all_reasoning.append(f"[命令生成] {cmd_result['reasoning']}")

        print(f"[Workflow] 风险评估: {risk_assessment}")
        print(f"[Workflow] 生成命令: {cmd_result.get('command', '')}")

        # 3. 安全校验（纯同步，不调用 LLM）
        validation = self.validator.check_safety(
            cmd_result.get("command", ""),
            risk_assessment.get("risk_level", ""),
        )
        validation["explanation"] = cmd_result.get("explanation", validation.get("explanation", ""))
        print(f"[Workflow] 命令校验: {validation}")

        # 如果命令被拦截，直接报告
        if validation.get("is_blocked"):
            rep_result = await self.reporter.report(
                task_plan, risk_assessment, validation, {}, {},
                memories=memories, knowledge_context=knowledge_context,
            )
            if rep_result.get("reasoning"):
                all_reasoning.append(f"[报告生成] {rep_result['reasoning']}")
            return {
                "answer": rep_result.get("answer", ""),
                "reasoning": "\n\n".join(all_reasoning),
                "task_plan": task_plan,
                "risk_assessment": risk_assessment,
                "validation": validation,
            }

        # 4. Executor — 执行命令（带反馈循环）
        execution_result, observation = await self._execute_with_feedback(
            task_plan, validation, risk_assessment, memories=memories
        )

        # 5. Reporter — 汇总报告
        rep_result = await self.reporter.report(
            task_plan, risk_assessment, validation,
            execution_result, observation,
            memories=memories, knowledge_context=knowledge_context,
        )
        if rep_result.get("reasoning"):
            all_reasoning.append(f"[报告生成] {rep_result['reasoning']}")

        return {
            "answer": rep_result.get("answer", ""),
            "reasoning": "\n\n".join(all_reasoning),
            "task_plan": task_plan,
            "risk_assessment": risk_assessment,
            "validation": validation,
            "execution_result": execution_result,
            "observation": observation,
        }

    async def _execute_with_feedback(
        self, task_plan: dict, validation: dict, risk_assessment: dict, memories: list = None
    ) -> tuple:
        """
        执行命令 + Observer 观察，支持反馈循环
        如果 Observer 判断需要重试，则回到 Validator 重新生成命令
        """
        for loop_idx in range(MAX_RETRY_LOOPS + 1):
            # 执行命令
            execution_result = await self.executor.execute(validation["command"])
            print(f"[Workflow] 执行结果 (loop {loop_idx}): {execution_result.get('success')}")

            # Observer 观察
            obs_result = await self.observer.observe(task_plan, execution_result)
            observation = obs_result["observation"]
            print(f"[Workflow] 观察结果 (loop {loop_idx}): {observation.get('status')}")

            # 判断是否需要重试
            if observation.get("needs_retry") and loop_idx < MAX_RETRY_LOOPS:
                print(f"[Workflow] Observer 建议重试，重新生成命令...")
                # 用 Observer 的建议重新生成命令
                retry_cmd = await self.validator.generate_command_with_feedback(
                    task_plan=task_plan,
                    memories=memories,
                    previous_command=validation["command"],
                    execution_output=execution_result.get("result", ""),
                    observation_feedback=observation.get("retry_suggestion", ""),
                )
                if retry_cmd.get("command"):
                    # 循环保护：重新生成的命令与上一轮完全相同 -> 视为无进展，停止重试
                    if self._canonical_command(retry_cmd["command"]) == self._canonical_command(validation["command"]):
                        print("[Workflow] 重试命令与上一轮相同，停止重试")
                        return execution_result, observation
                    validation["command"] = retry_cmd["command"]
                    validation["explanation"] = retry_cmd.get("explanation", "重试命令")
                    continue

            return execution_result, observation

        return execution_result, observation

    async def run_stream(
        self,
        user_id: str,
        user_message: str,
        memories: list = None,
        knowledge_context: str = "",
        host: str = None,
        port: int = None,
        username: str = None,
        password: str = None,
        conversation_history: list = None,
    ):
        """
        运行工作流（流式），yield SSE 事件
        支持并行执行、思考链推送、反馈循环

        事件类型:
            {"type": "workflow_status", "stage": "...", "message": "..."}  # 工作流阶段
            {"type": "model_info", "model": "...", "display": "..."}       # 当前模型信息
            {"type": "reasoning", "agent": "...", "content": "..."}        # 各 Agent 思考链
            {"type": "task_plan", "content": {...}}
            {"type": "risk_assessment", "content": {...}}
            {"type": "validation", "content": {...}}
            {"type": "tool_call", "tool": "...", "command": "..."}
            {"type": "tool_result", "tool": "...", "result": "..."}
            {"type": "observation", "content": {...}}
            {"type": "retry_loop", "loop": int, "reason": "..."}           # 反馈循环重试
            {"type": "answer_reasoning", "content": "..."}                 # Reporter 思考链
            {"type": "answer_chunk", "content": "..."}                     # Reporter 正文
            {"type": "done"}
            {"type": "error", "content": "..."}
        """
        print(f"[Workflow Stream] 用户 {user_id} 发起请求: {user_message}")

        # 发送当前模型信息
        yield {
            "type": "model_info",
            "model": get_current_model_display(),
            "models": get_model_status(),
        }

        try:
            # 0. CommandRewriter — 重写用户模糊问题
            yield {"type": "workflow_status", "stage": "rewriter", "message": "正在理解您的问题..."}
            print("[Workflow Stream] 步骤0: CommandRewriter 重写用户问题...")
            rewrite_result = await self.command_rewriter.rewrite(user_message, conversation_history=conversation_history)
            rewritten_message = rewrite_result.get("rewritten", user_message)
            if rewrite_result["reasoning"]:
                yield {"type": "reasoning", "agent": "command_rewriter", "content": rewrite_result["reasoning"]}
            
            # 只要改写后的内容确实改变，就展示“问题已重写”，方便确认重写是否合理
            if rewritten_message != user_message:
                yield {
                    "type": "command_rewritten",
                    "original": user_message,
                    "rewritten": rewritten_message,
                    "key_entities": rewrite_result.get("key_entities", {}),
                }
                print(f"[Workflow Stream] 问题已重写: {user_message} → {rewritten_message}")
            
            # 如果需要向用户澄清，将澄清问题作为回答输出（不阻断流程，让用户继续对话）
            if rewrite_result.get("clarification_needed") and rewrite_result.get("clarification_question"):
                yield {
                    "type": "clarification_needed",
                    "question": rewrite_result["clarification_question"],
                }
                # 不 return，继续走 Orchestrator 流程
                # Orchestrator 会基于重写后的问题尝试给出最佳回答

            # 1. Orchestrator — 使用重写后的问题分析意图
            yield {"type": "workflow_status", "stage": "orchestrator", "message": "正在分析意图..."}
            print("[Workflow Stream] 步骤1: Orchestrator 分析意图...")
            try:
                orc_result = await self.orchestrator.analyze(rewritten_message, conversation_history=conversation_history)
                task_plan = orc_result["task_plan"]
                print(f"[Workflow Stream] task_plan: {task_plan}")
                if orc_result["reasoning"]:
                    yield {"type": "reasoning", "agent": "orchestrator", "content": orc_result["reasoning"]}
                yield {"type": "task_plan", "content": task_plan}
            except Exception as e:
                print(f"[Workflow Stream] Orchestrator 分析失败: {e}")
                traceback.print_exc()
                yield {"type": "error", "content": f"意图分析失败: {e}"}
                return

            # 检查 task_plan 是否有效（LLM 可能返回空结果）
            if not task_plan or not task_plan.get("intent"):
                print(f"[Workflow Stream] Orchestrator 返回空 task_plan，LLM 可能不可用")
                yield {"type": "error", "content": "⚠️ AI 服务暂时不可用，请稍后重试。如果问题持续，请检查 LLM API 配置。"}
                yield {"type": "done"}
                return

            # 安全兜底：纯理论知识/概念询问，不需要执行
            # 例如"什么是 Deployment"、"Kubernetes 是什么"等
            # 但"显示 Pod"、"查看容器"等查询集群状态的请求需要执行
            if (
                task_plan.get("intent") == "query"
                and task_plan.get("task_type") == "other"
                and task_plan.get("target") == "unknown"
            ):
                task_plan["requires_execution"] = False

            # 不需要执行（聊天/知识问答/查询）
            if not task_plan.get("requires_execution"):
                yield {"type": "workflow_status", "stage": "reporter", "message": "正在生成回答..."}
                # 使用聊天式 prompt，让回答更自然
                chat_prompt = "你是 Kubedoctor，一个友好的 Kubernetes 运维助手。请用自然、对话式的中文回答用户的问题。不要使用报告格式，就像朋友聊天一样。如果用户问的是技术问题，给出专业但易懂的回答。"
                if knowledge_context:
                    chat_prompt += f"\n\n参考知识库：\n{knowledge_context}"
                if conversation_history:
                    history_text = "\n".join([f"{'用户' if m['role'] == 'user' else '你'}: {m['content'][:200]}" for m in conversation_history[-5:]])
                    chat_prompt += f"\n\n当前对话历史（最近5条）：\n{history_text}"
                if memories:
                    memory_text = "\n".join([f"- {m.content}" for m in memories[:3]])
                    chat_prompt += (
                        "\n\n用户的历史记忆（长期记忆，反映用户真实偏好与事实）：\n" + memory_text +
                        "\n提示：这些是用户明确表达过的偏好/事实，应予以尊重——包括实际执行/建议操作时优先采用用户偏好的工具（如偏好 nerdctl 则用 nerdctl）。若用户是在询问“选哪个/哪个更好/比较 A 和 B”，请同时客观对比两者的适用场景与利弊，给出均衡建议，不要单边站队。" +
                        "\n特别提示：当用户问\u201c我喜欢 A 还是 B / 我的偏好是 / 我该用哪个\u201d这类关于【用户自己】偏好的问题时，必须基于上述记忆直接、明确地告诉用户 TA 自己的既有选择或偏好（例如：根据你的长期记忆，你更偏好 nerdctl），并用\u201c你\u201d来表述，而不是以\u201c我（助手）更喜欢 X\u201d来回答，避免答非所问。"
                    )
                
                has_content = False
                async for event in self.reporter.think_stream(
                    system_prompt=chat_prompt,
                    user_message=rewritten_message,
                ):
                    if event.get("type") == "content" and event.get("content"):
                        has_content = True
                        yield {"type": "answer_chunk", "content": event["content"]}
                    elif event.get("type") == "reasoning":
                        yield {"type": "answer_reasoning", "content": event["content"]}
                    elif event.get("type") == "model_switched":
                        yield event
                if not has_content:
                    yield {"type": "answer_chunk", "content": "⚠️ AI 服务暂时不可用，请稍后重试。如果问题持续，请检查 LLM API 配置。"}
                yield {"type": "done"}
                return

            # 2. 并行执行：Risk Assessor + Validator 命令生成
            yield {"type": "workflow_status", "stage": "risk_validator", "message": "正在评估风险并生成命令..."}
            print("[Workflow Stream] 步骤2: 并行执行风险评估 + 命令生成...")
            risk_task = self.risk_assessor.assess(task_plan)
            cmd_task = self.validator.generate_command(task_plan, memories=memories)

            risk_result, cmd_result = await asyncio.gather(risk_task, cmd_task)
            print(f"[Workflow Stream] risk_result keys: {list(risk_result.keys())}")
            print(f"[Workflow Stream] cmd_result: {cmd_result}")

            risk_assessment = risk_result["risk_assessment"]
            if risk_result["reasoning"]:
                yield {"type": "reasoning", "agent": "risk_assessor", "content": risk_result["reasoning"]}
            yield {"type": "risk_assessment", "content": risk_assessment}
            # 短暂延迟，让前端有时间渲染风险评估模块
            await asyncio.sleep(0.3)

            if cmd_result["reasoning"]:
                yield {"type": "reasoning", "agent": "validator", "content": cmd_result["reasoning"]}

            # 3. 安全校验（纯同步）
            validation = self.validator.check_safety(
                cmd_result.get("command", ""),
                risk_assessment.get("risk_level", ""),
            )
            validation["explanation"] = cmd_result.get("explanation", validation.get("explanation", ""))
            yield {"type": "validation", "content": validation}
            # 短暂延迟，让前端有时间渲染命令校验模块
            await asyncio.sleep(0.3)

            # 命令被拦截：统一改为弹确认窗让用户决定是否放行执行
            # （校验器若只给了风险说明而未生成具体命令，则从任务计划兜底构造可执行命令）
            if validation.get("is_blocked"):
                blocked_cmd = (validation.get("command") or "").strip()
                if not blocked_cmd:
                    blocked_cmd = self._build_execution_command(task_plan)
                    if blocked_cmd:
                        validation["command"] = blocked_cmd

                # 弹确认窗，由用户决定是否放行执行
                if blocked_cmd:
                    confirm_label = f"✅ 确认执行：{blocked_cmd[:80]}"
                else:
                    confirm_label = "✅ 确认继续处理"
                yield {
                    "type": "confirm_required",
                    "risk_level": "dangerous",
                    "command": blocked_cmd,
                    "explanation": f"{validation.get('explanation', '安全校验未通过')}（已改为由你确认后再执行）",
                    "reason": "该操作触发了安全拦截，是否确认放行执行？",
                    "options": [
                        {"id": "execute", "label": confirm_label, "value": "execute"},
                        {"id": "cancel", "label": "❌ 取消执行", "value": "cancel"},
                    ],
                }
                import asyncio as _asyncio2
                confirm_event = _asyncio2.Event()
                user_choice = {"value": None}
                from app.llm.agents import _pending_confirmations
                confirm_id = id(confirm_event)
                _pending_confirmations[confirm_id] = {
                    "event": confirm_event, "choice": user_choice,
                }
                yield {"type": "confirm_id", "confirm_id": confirm_id}
                try:
                    await _asyncio2.wait_for(confirm_event.wait(), timeout=120.0)
                except _asyncio2.TimeoutError:
                    _pending_confirmations.pop(confirm_id, None)
                    yield {"type": "answer_chunk", "content": "\n\n⏱️ 确认超时，操作已取消。"}
                    yield {"type": "done"}
                    return
                _pending_confirmations.pop(confirm_id, None)
                if user_choice["value"] == "execute":
                    # 用户确认放行，继续执行，且不再重复弹窗（不向回复注入确认文本）
                    validation["is_blocked"] = False
                    risk_assessment["requires_confirm"] = False
                else:
                    yield {"type": "answer_chunk", "content": "❌ 操作已取消。"}
                    yield {"type": "done"}
                    return

            # 3.5 交互式确认：如果风险等级需要确认，发送确认请求给前端
            # 测试模式下跳过确认
            # 如果置信度 >= 80%，自动执行，不需要用户确认
            from app.core.config import TEST_MODE
            confidence = risk_assessment.get("confidence", 0)
            _cmd = (validation.get("command") or "").strip().lower()
            _readonly = not _cmd or _cmd.startswith((
                "kubectl get ", "kubectl describe ", "kubectl logs ",
                "kubectl top ", "kubectl version", "kubectl cluster-info",
                "kubectl explain", "kubectl auth ", "kubectl api-",
                "kubectl diff ", "kubectl options",
            ))
            if not TEST_MODE and not _readonly and risk_assessment.get("requires_confirm") and risk_assessment.get("risk_level") in ("dangerous", "critical"):
                # 如果置信度 >= 80%，自动执行，跳过用户确认
                if confidence >= AUTO_EXEC_CONFIDENCE:
                    yield {
                        "type": "auto_fix",
                        "content": f"🤖 置信度 {confidence*100:.0f}%，自动执行: {validation.get('command', '')}",
                    }
                else:
                    # 生成替代方案选项
                    suggestions = risk_assessment.get("suggestions", "")
                    confirm_options = [
                        {"id": "execute", "label": f"✅ 确认执行: {validation.get('command', '')}", "value": "execute"},
                    ]
                    if suggestions:
                        confirm_options.append({"id": "alternative", "label": f"💡 采用建议: {suggestions}", "value": "alternative"})
                    confirm_options.append({"id": "cancel", "label": "❌ 取消执行", "value": "cancel"})

                    yield {
                        "type": "confirm_required",
                        "risk_level": risk_assessment.get("risk_level"),
                        "command": validation.get("command", ""),
                        "explanation": validation.get("explanation", ""),
                        "reason": risk_assessment.get("reason", ""),
                        "suggestions": suggestions,
                        "options": confirm_options,
                    }

                    # 等待用户确认（通过 asyncio.Event）
                    import asyncio as _asyncio
                    confirm_event = _asyncio.Event()
                    user_choice = {"value": None}

                    # 将确认事件存入全局字典，供 API 层设置
                    from app.llm.agents import _pending_confirmations
                    confirm_id = id(confirm_event)
                    _pending_confirmations[confirm_id] = {
                        "event": confirm_event,
                        "choice": user_choice,
                    }

                    yield {"type": "confirm_id", "confirm_id": confirm_id}

                    # 等待用户响应（超时 120 秒）
                    try:
                        await _asyncio.wait_for(confirm_event.wait(), timeout=120.0)
                    except _asyncio.TimeoutError:
                        yield {"type": "answer_chunk", "content": "\n\n⏱️ 确认超时，操作已取消。"}
                        yield {"type": "done"}
                        return

                    # 清理
                    _pending_confirmations.pop(confirm_id, None)

                    choice = user_choice["value"]
                    if choice == "cancel":
                        yield {"type": "answer_chunk", "content": "❌ 操作已取消。"}
                        yield {"type": "done"}
                        return
                    elif choice == "alternative" and suggestions:
                        # 使用建议作为新命令
                        yield {"type": "answer_chunk", "content": f"💡 采用建议方案，请重新描述您的需求。"}
                        yield {"type": "done"}
                        return
                    # choice == "execute" → 继续执行

            # 4. 执行 + 观察 + 反馈循环（持续直到问题解决）
            MAX_ITERATIONS = MAX_AGENT_ITERATIONS
            # 循环保护：防止重复调用同一工具陷入死循环
            # - seen_command_outcomes: 记录 (命令指纹, 结果指纹)，检测硬性重复
            # - no_progress_streak: 连续无进展轮数，达到阈值即停止自动重试
            # - prev_obs_sig: 上一轮观察签名，检测"换思路但依旧无进展"
            seen_command_outcomes = set()
            seen_commands = set()   # 已执行过的命令（规范化），用于避免重复推荐/重复调用
            no_progress_streak = 0
            prev_obs_sig = None
            iteration = 0
            all_execution_results = []
            all_observations = []

            while iteration < MAX_ITERATIONS:
                iteration += 1

                # 4a. Executor
                command = validation.get("command", "")
                yield {"type": "workflow_status", "stage": "executor", "message": f"正在执行命令... (第{iteration}轮)"}
                print(f"[Workflow Stream] 步骤4 (iteration {iteration}): 执行命令: {command}")
                yield {"type": "tool_call", "tool": "execute_command", "command": command}

                execution_result = await self.executor.execute(
                    command, host=host, port=port, username=username, password=password
                )
                all_execution_results.append(execution_result)
                print(f"[Workflow Stream] 执行结果 success={execution_result.get('success')}")
                print(f"[Workflow Stream] 执行结果 output={str(execution_result.get('result', ''))[:300]}")
                yield {
                    "type": "tool_result",
                    "tool": "execute_command",
                    "command": command,
                    "result": str(execution_result.get("result", ""))[:500],
                    "success": execution_result.get("success", False),
                }
                # 图沉淀：写命令涉及的资源记录操作审计（后台异步，不阻塞回复）。
                # K8s 拓扑一律由「集群拓扑索引器」按 kubectl -o json 全量重建，不再从命令输出解析。
                if execution_result.get("success") and command.strip():
                    _entities = self._extract_k8s_entities(command)
                    if _entities:
                        asyncio.create_task(self._persist_tool_graph(
                            user_id, command, str(execution_result.get("result", "")), _entities
                        ))



                # 4b. Observer
                yield {"type": "workflow_status", "stage": "observer", "message": "正在观察结果..."}
                obs_result = await self.observer.observe(task_plan, execution_result)
                if obs_result["reasoning"]:
                    yield {"type": "reasoning", "agent": "observer", "content": obs_result["reasoning"]}
                yield {"type": "observation", "content": obs_result["observation"]}

                observation = obs_result["observation"]
                all_observations.append(observation)

                # 判断问题是否已解决
                # 注意：即使 status 是 healthy，如果用户意图是诊断问题且发现了异常，
                # 也应该继续循环尝试修复
                is_resolved = (
                    observation.get("status") == "healthy"
                    and observation.get("success")
                    and not self._has_pending_issues(observation, task_plan)
                )
                if is_resolved:
                    yield {"type": "workflow_status", "stage": "resolved", "message": "✅ 问题已解决！"}
                    break

                # 纯查询操作（intent=query），即使发现异常也不进入修复循环
                # 用户只是想查看状态，不是要诊断或修复问题
                if task_plan.get("intent") == "query":
                    yield {"type": "workflow_status", "stage": "query_complete", "message": "📋 查询完成，正在生成报告..."}
                    break

                # ── 循环保护：检测重复执行 / 连续无进展，避免工具调用死循环 ──
                cmd_key = self._canonical_command(command)
                outcome_key = self._outcome_fingerprint(execution_result)
                hard_repeat = (cmd_key, outcome_key) in seen_command_outcomes
                obs_sig = f"{observation.get('status')}|{observation.get('findings')}"
                obs_unchanged = (prev_obs_sig is not None and obs_sig == prev_obs_sig)

                if hard_repeat or obs_unchanged:
                    no_progress_streak += 1
                else:
                    no_progress_streak = 0
                seen_command_outcomes.add((cmd_key, outcome_key))
                seen_commands.add(cmd_key)
                prev_obs_sig = obs_sig

                # 循环保护：达到阈值时不直接进入报告阶段，而是强制交由用户决策下一步
                force_user_choice = no_progress_streak >= LOOP_NO_PROGRESS_LIMIT
                if force_user_choice:
                    print(f"[Workflow Stream] 检测到连续 {no_progress_streak} 轮无进展，交由用户决策")
                    yield {"type": "workflow_status", "stage": "planning_next", "message": f"⚠️ 检测到连续 {no_progress_streak} 轮未取得进展，请选择下一步处理方式..."}
                else:
                    # 如果问题未解决，尝试自动生成修复方案
                    yield {"type": "workflow_status", "stage": "planning_next", "message": "🔄 问题未解决，正在分析下一步..."}

                # 用 LLM 生成多个修复选项
                fix_options = await self._generate_fix_options(
                    task_plan=task_plan,
                    memories=memories,
                    execution_result=execution_result,
                    observation=observation,
                    all_results=all_execution_results,
                    all_observations=all_observations,
                    iteration=iteration,
                )

                if fix_options and len(fix_options) >= 1:
                    # 检查是否有任意方案置信度 >= 80%，自动选择最高置信度的方案
                    best_option = max(fix_options, key=lambda x: x.get("confidence", 0))
                    if best_option.get("confidence", 0) >= AUTO_EXEC_CONFIDENCE and not force_user_choice:
                        chosen = best_option
                        yield {"type": "auto_fix", "content": f"🤖 置信度 {chosen.get('confidence', 0)*100:.0f}%，自动执行: {chosen.get('description', '')}"}
                        validation["command"] = chosen.get("command", "")
                        validation["explanation"] = chosen.get("description", "")
                        # 更新 task_plan 以反映新的诊断方向
                        task_plan["description"] = chosen.get("description", task_plan.get("description", ""))
                        continue

                    # 所有方案置信度都 < 80% → 让用户选择
                    # 过滤掉已尝试过的命令（避免重复推荐导致循环），并重新编号
                    options = []
                    known = set()
                    for opt in fix_options[:3]:  # 最多 3 个选项
                        oc = self._canonical_command(opt.get("command", ""))
                        if oc and (oc in seen_commands or oc in known):
                            continue
                        if oc:
                            known.add(oc)
                        options.append({
                            "id": f"option_{len(options)}",
                            "label": f"{'✅' if len(options) == 0 else '💡'} {opt.get('description', f'方案 {len(options)+1}')}",
                            "command": opt.get("command", ""),
                            "description": opt.get("description", ""),
                            "confidence": opt.get("confidence", 0),
                        })
                    if not options:
                        # 所有方案都已试过：无法再自动推进，放弃进入报告
                        yield {"type": "workflow_status", "stage": "planning_next", "message": "⚠️ 可选的修复方案均已尝试且未解决，正在生成诊断报告..."}
                        break

                    dialog_msg = (
                        "⚠️ 连续执行未取得进展，请选择下一步处理方式："
                        if force_user_choice
                        else "🔍 发现以下可能的解决方案，请选择一个："
                    )
                    yield {
                        "type": "fix_options",
                        "message": dialog_msg,
                        "options": options,
                        "observation_summary": observation.get("findings", ""),
                    }

                    # 等待用户选择
                    import asyncio as _asyncio
                    choice_event = _asyncio.Event()
                    user_choice = {"value": None}

                    from app.llm.agents import _pending_confirmations
                    choice_id = id(choice_event)
                    _pending_confirmations[choice_id] = {
                        "event": choice_event,
                        "choice": user_choice,
                    }

                    yield {"type": "choice_required", "choice_id": choice_id}

                    try:
                        await _asyncio.wait_for(choice_event.wait(), timeout=300.0)
                    except _asyncio.TimeoutError:
                        _pending_confirmations.pop(choice_id, None)
                        yield {"type": "answer_chunk", "content": "\n\n⏱️ 选择超时，操作已取消。"}
                        yield {"type": "done"}
                        return

                    _pending_confirmations.pop(choice_id, None)
                    chosen_option = user_choice["value"]

                    if chosen_option == "cancel":
                        yield {"type": "answer_chunk", "content": "❌ 已取消操作，正在生成诊断报告..."}
                        # 跳转到 Reporter 生成报告
                        break
                    elif chosen_option == "skip":
                        yield {"type": "answer_chunk", "content": "⏭️ 已跳过，正在生成诊断报告..."}
                        # 跳转到 Reporter 生成报告
                        break
                    elif chosen_option and chosen_option.startswith("option_"):
                        idx = int(chosen_option.split("_")[1])
                        if idx < len(options):
                            chosen = options[idx]
                            validation["command"] = chosen["command"]
                            validation["explanation"] = chosen["description"]
                            task_plan["description"] = chosen["description"]
                            yield {"type": "user_choice_applied", "content": f"✅ 已选择: {chosen['description']}"}
                            continue
                        else:
                            yield {"type": "answer_chunk", "content": "❌ 无效选择，操作已取消。"}
                            yield {"type": "done"}
                            return
                    else:
                        yield {"type": "answer_chunk", "content": "❌ 操作已取消。"}
                        yield {"type": "done"}
                        return
                else:
                    # 无法生成修复方案，直接进入 Reporter 生成报告
                    yield {"type": "workflow_status", "stage": "planning_next", "message": "⚠️ 无法自动确定下一步，正在生成诊断报告..."}
                    break

            # 5. Reporter — 流式输出（传入所有轮次的结果）
            yield {"type": "workflow_status", "stage": "reporter", "message": "正在生成报告..."}
            async for event in self.reporter.report_stream(
                task_plan, risk_assessment, validation,
                execution_result, observation,
                memories=memories, knowledge_context=knowledge_context,
                all_execution_results=all_execution_results,
                all_observations=all_observations,
            ):
                if event["type"] == "reasoning":
                    yield {"type": "answer_reasoning", "content": event["content"]}
                elif event["type"] == "model_switched":
                    yield event
                elif event["type"] == "content":
                    yield {"type": "answer_chunk", "content": event["content"]}
                else:
                    yield event

            yield {"type": "done"}

        except Exception as e:
            print(f"[Workflow Stream] 异常: {e}")
            traceback.print_exc()
            yield {"type": "error", "content": str(e)}

    @staticmethod
    def _create_pod_command(command: str, namespace: str = "") -> str:
        """把 create-pod 任务里的 create deployment 命令改写成 kubectl run(建真正 Pod)"""
        import re as _re
        ns_flag = f" -n {namespace}" if namespace else ""
        out = []
        for p in _re.split(r"\s*&&\s*", command or ""):
            m = _re.match(r"kubectl create deployment\s+([\w.-]+)(.*)", p.strip())
            if not m:
                out.append(p)
                continue
            name = m.group(1)
            rest = m.group(2) or ""
            img = _re.search(r"--image=([\S]+)", rest)
            image = img.group(1) if img else "nginx:latest"
            out.append(f"kubectl run {name} --image={image}{ns_flag}")
        return " && ".join(out)


    @staticmethod
    def _parse_pod_rows(tool_result: str) -> list:
        """从 kubectl get pods 输出里解析 Pod 名及其控制器归属

        - StatefulSet: <name>-<序号>（序号为纯数字且无 hash，如 web-0）
        - Deployment / DaemonSet / Job: <name>-<hash>-<随机>，仅默认 Deployment；
          仅凭 get pods 无法区分三者，如需精确归属应改用 get deploy,sts,ds,job 联合解析。
        """
        rows = []
        for line in (tool_result or "").splitlines():
            line = line.strip()
            if not line:
                continue
            cols = line.split()
            if not cols:
                continue
            first = cols[0]
            if first in ("NAME", "No", "Error"):
                continue
            parts = first.split("-")
            if len(parts) < 2:
                continue
            # StatefulSet: 最后一段是序号（纯数字）
            if parts[-1].isdigit():
                controller = "-".join(parts[:-1])
                if controller:
                    rows.append({"pod": first, "controller_type": "StatefulSet", "controller": controller, "replicaset": None})
                continue
            # Deployment/DaemonSet/Job 命名相同：<name>-<hash>-<随机>
            if len(parts) < 3:
                continue
            controller = "-".join(parts[:-2])
            replicaset = "-".join(parts[:-1])
            if not controller:
                continue
            rows.append({"pod": first, "controller_type": "Deployment", "controller": controller, "replicaset": replicaset})
        return rows

    async def _persist_pod_topology(self, owner: str, tool_result: str, namespace: str):
        """后台把 Pod→ReplicaSet→Deployment 拓扑写入 Neo4j（失败仅打印，不阻塞主流程）"""
        try:
            rows = self._parse_pod_rows(tool_result)
            if not rows:
                return
            from app.memory.repository.graph_repository import GraphRepository
            from app.db.neo4j import neo4j
            repo = GraphRepository(driver=neo4j.get_driver())
            await repo.sync_pod_topology(owner, namespace, rows)
        except Exception as e:
            print(f"[Neo4j 拓扑同步] 失败: {type(e).__name__}: {e}")


    @staticmethod
    def _classify_get_resource(command: str):
        """识别 kubectl get 的资源类型，返回 (NodeType标签, cluster_scoped) 或 None"""
        m = re.search(r"kubectl\s+get\s+([\w\-,\.]+)", command or "")
        if not m:
            return None
        tok = m.group(1).split(",")[0].strip().lower()
        mapping = {
            "svc": ("Service", False), "service": ("Service", False), "services": ("Service", False),
            "endpoints": ("Endpoints", False), "ep": ("Endpoints", False),
            "ingress": ("Ingress", False), "ing": ("Ingress", False),
            "configmap": ("ConfigMap", False), "cm": ("ConfigMap", False),
            "secret": ("Secret", False), "secrets": ("Secret", False),
            "role": ("Role", False), "roles": ("Role", False),
            "clusterrole": ("ClusterRole", True), "clusterroles": ("ClusterRole", True),
            "rolebinding": ("RoleBinding", False), "rolebindings": ("RoleBinding", False),
            "clusterrolebinding": ("ClusterRoleBinding", True), "clusterrolebindings": ("ClusterRoleBinding", True),
            "sa": ("ServiceAccount", False), "serviceaccount": ("ServiceAccount", False), "serviceaccounts": ("ServiceAccount", False),
            "pvc": ("PersistentVolumeClaim", False), "pv": ("PersistentVolume", True),
            "storageclass": ("StorageClass", True), "sc": ("StorageClass", True),
            "cronjob": ("CronJob", False), "cj": ("CronJob", False),
        }
        return mapping.get(tok)

    @staticmethod
    def _parse_name_rows(tool_result: str) -> list:
        """从 get 输出第一列解析资源名列表（跳过 NAME/No 等表头）"""
        names = []
        for line in (tool_result or "").splitlines():
            line = line.strip()
            if not line:
                continue
            cols = line.split()
            if not cols:
                continue
            first = cols[0]
            if first in ("NAME", "No", "Error"):
                continue
            names.append(first)
        return names

    @staticmethod
    def _parse_rbac_rows(tool_result: str, is_cluster: bool) -> list:
        """解析 rolebindings/clusterrolebindings 的 -o wide 输出 → 每条 binding+role+subjects

        wide 格式: NAME ROLE USERS GROUPS SERVICEACCOUNTS
        """
        rows = []
        for line in (tool_result or "").splitlines():
            line = line.strip()
            if not line or not line.split():
                continue
            cols = line.split()
            first = cols[0]
            if first in ("NAME", "No", "Error", "Found"):
                continue
            if len(cols) < 2:
                continue
            name = cols[0]
            if name.lower() == "role":
                continue
            role_cell = cols[1]
            role = None
            role_kind = "ClusterRole"
            if "/" in role_cell:
                rk, _, rn = role_cell.partition("/")
                role_kind = rk if rk in ("Role", "ClusterRole") else "ClusterRole"
                role = rn
            else:
                role = role_cell
            rest = cols[2:]
            subjects = []
            def add(typ, cell):
                if cell and cell != "<none>":
                    for item in cell.split(","):
                        item = item.strip()
                        if item:
                            subjects.append({"type": typ, "name": item})
            if is_cluster:
                # clusterrolebindings: NAME ROLE USERS GROUPS SERVICEACCOUNTS
                add("User", rest[0] if len(rest) >= 1 else "")
                add("Group", rest[1] if len(rest) >= 2 else "")
                add("ServiceAccount", rest[2] if len(rest) >= 3 else "")
            else:
                # rolebindings: NAME ROLE USERS GROUPS SERVICEACCOUNTS
                add("User", rest[0] if len(rest) >= 1 else "")
                add("Group", rest[1] if len(rest) >= 2 else "")
                add("ServiceAccount", rest[2] if len(rest) >= 3 else "")
            rows.append({
                "kind": "ClusterRoleBinding" if is_cluster else "RoleBinding",
                "name": name,
                "role": role,
                "role_kind": role_kind,
                "subjects": subjects,
            })
        return rows

    async def _persist_list_topology(self, owner, label, cluster_scoped, tool_result, namespace):
        """后台把 get <资源> 列表写入 Neo4j（失败仅打印）"""
        try:
            names = self._parse_name_rows(tool_result)
            if not names:
                return
            rows = [{"type": label, "name": n} for n in names]
            from app.memory.repository.graph_repository import GraphRepository
            from app.db.neo4j import neo4j
            repo = GraphRepository(driver=neo4j.get_driver())
            await repo.sync_resource_list(owner, namespace, rows, cluster_scoped=cluster_scoped)
        except Exception as e:
            print(f"[Neo4j 拓扑同步] 失败: {type(e).__name__}: {e}")

    async def _persist_endpoints_topology(self, owner, tool_result, namespace):
        try:
            names = self._parse_name_rows(tool_result)
            if not names:
                return
            rows = [{"service": n} for n in names]
            from app.memory.repository.graph_repository import GraphRepository
            from app.db.neo4j import neo4j
            repo = GraphRepository(driver=neo4j.get_driver())
            await repo.sync_endpoints(owner, namespace, rows)
        except Exception as e:
            print(f"[Neo4j 拓扑同步] endpoints 失败: {type(e).__name__}: {e}")

    async def _persist_rbac_topology(self, owner, tool_result, is_cluster, namespace):
        try:
            rows = self._parse_rbac_rows(tool_result, is_cluster)
            if not rows:
                return
            for rb in rows:
                if not is_cluster:
                    rb["namespace"] = namespace or "default"
            from app.memory.repository.graph_repository import GraphRepository
            from app.db.neo4j import neo4j
            repo = GraphRepository(driver=neo4j.get_driver())
            await repo.sync_rbac(owner, rows)
        except Exception as e:
            print(f"[Neo4j 拓扑同步] rbac 失败: {type(e).__name__}: {e}")

    @staticmethod
    def _extract_k8s_entities(command: str) -> list:
        """从 kubectl 命令中提取涉及的资源实体（Deployment/nginx-a、Namespace/default 等）"""
        WRITE_VERBS = {
            "create", "apply", "delete", "scale", "rollout", "restart",
            "run", "expose", "edit", "patch", "label", "annotate",
            "wait", "exec", "drain", "cordon", "uncordon", "taint",
        }
        VALUE_FLAGS = {
            "-o", "--output", "-l", "--selector", "--field-selector",
            "--sort-by", "--request-timeout", "--timeout", "--grace-period",
            "--ignore-not-found", "-w", "--watch", "--cascade",
        }
        res_types = {
            "deployment": "Deployment", "deploy": "Deployment",
            "pod": "Pod", "pods": "Pod",
            "service": "Service", "svc": "Service",
            "endpoints": "Endpoints", "ep": "Endpoints",
            "statefulset": "StatefulSet", "sts": "StatefulSet",
            "daemonset": "DaemonSet", "ds": "DaemonSet",
            "job": "Job", "cronjob": "CronJob", "cj": "CronJob",
            "configmap": "ConfigMap", "cm": "ConfigMap",
            "secret": "Secret",
            "role": "Role", "roles": "Role",
            "clusterrole": "ClusterRole", "clusterroles": "ClusterRole",
            "rolebinding": "RoleBinding", "rolebindings": "RoleBinding",
            "clusterrolebinding": "ClusterRoleBinding", "clusterrolebindings": "ClusterRoleBinding",
            "serviceaccount": "ServiceAccount", "sa": "ServiceAccount",
            "namespace": "Namespace", "ns": "Namespace",
            "node": "Node", "nodes": "Node",
            "pvc": "PersistentVolumeClaim", "pv": "PersistentVolume",
            "storageclass": "StorageClass", "sc": "StorageClass",
            "ingress": "Ingress", "ing": "Ingress",
        }
        entities: list = []
        m_ns = re.search(r"(?:-n|--namespace)\s+([\w.-]+)", command or "")
        if m_ns:
            entities.append(f"Namespace/{m_ns.group(1)}")

        for part in re.split(r"[;&|]{1,2}", command or ""):
            part = part.strip()
            if not part.startswith("kubectl"):
                continue
            tokens = part.split()
            verb_idx = -1
            verb = None
            for i, t in enumerate(tokens[1:], start=1):
                if t in WRITE_VERBS or t in ("get", "describe", "logs", "top"):
                    verb = t
                    verb_idx = i
                    break
            if verb not in WRITE_VERBS:
                continue
            if verb == "rollout":
                verb_idx += 1  # 跳过 restart/undo/status 等子命令
            if verb == "run":
                # kubectl run <name> 会直接创建一个 Pod（没有资源类型 token）
                if verb_idx + 1 < len(tokens):
                    entities.append(f"Pod/{tokens[verb_idx + 1]}")
                continue
            restype = res_types.get(tokens[verb_idx + 1]) if verb_idx + 1 < len(tokens) else None
            if not restype:
                continue
            # 资源名：紧跟在资源类型后的第一个非 flag、非 flag 值的 token
            name = None
            j = verb_idx + 2
            while j < len(tokens):
                t = tokens[j]
                if t in VALUE_FLAGS:
                    j += 2
                    continue
                if t in ("-n", "--namespace"):
                    j += 2
                    continue
                if t.startswith("-"):
                    j += 1
                    continue
                name = t
                break
            if name:
                entities.append(f"{restype}/{name}")
        return entities


    async def _persist_tool_graph(self, owner: str, command: str, tool_result: str, entities: list):
        from app.core.config import NEO4J_WRITE_ENABLED
        if not NEO4J_WRITE_ENABLED:
            return
        """后台把执行命令涉及的资源写入 Neo4j 图（失败仅打印，不阻塞主流程）"""
        try:
            from app.memory.repository.graph_repository import GraphRepository
            from app.db.neo4j import neo4j
            repo = GraphRepository(driver=neo4j.get_driver())
            await repo.upsert_tool_entities(owner, command, tool_result, entities)
        except Exception as e:
            print(f"[Neo4j 写入] tool_entities 失败: {type(e).__name__}: {e}")

    def _build_execution_command(self, task_plan: dict) -> str:
        """
        当校验器未生成具体命令时，根据任务计划兜底构造一个可执行的 kubectl 命令。
        仅用于拼装确认弹窗内展示的命令，最终是否执行仍由用户在弹窗中决定。
        """
        try:
            task_type = str(task_plan.get("task_type") or "").lower()
            target = str(task_plan.get("target") or "resource").lower()
            raw_name = str(task_plan.get("resource_name") or "").strip()
            ns = str(task_plan.get("namespace") or "").strip()
            description = str(task_plan.get("description") or "")

            # 解析资源名称（支持逗号、中文逗号、顿号、空白分隔的多个名称）
            names = [n for n in re.split(r"[,，、\s]+", raw_name) if n]
            if not names:
                # 从描述中尽量识别资源名（k8s 命名规范：小写字母数字连字符）
                desc_names = re.findall(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", description)
                stop = {
                    "pod", "pods", "deployment", "deployments", "deploy",
                    "namespace", "namespaces", "default", "cluster", "node", "nodes",
                    "kubectl", "删除", "查看", "重启", "清理", "这些", "资源", "问题", "服务",
                }
                names = [n for n in desc_names if n not in stop and len(n) > 1][:5]

            nsarg = f" -n {ns}" if ns else ""
            is_delete = task_type in ("delete", "remove", "rm") or "删除" in description or "清理" in description
            is_restart = task_type in ("restart",) or ("重启" in description)

            if names:
                if is_delete:
                    target_type = "deployment" if target == "deployment" else ("pod" if target == "pod" else "deployment")
                    cmds = [f"kubectl delete {target_type} {n}{nsarg}" for n in names]
                    return " && ".join(cmds)
                if is_restart:
                    if target == "deployment":
                        cmds = [f"kubectl rollout restart deployment {n}{nsarg}" for n in names]
                    else:
                        cmds = [f"kubectl delete pod {n}{nsarg}" for n in names]
                    return " && ".join(cmds)
                # 其他操作回退为查询
                if target == "deployment":
                    return "kubectl get deployment -A -o wide"
                if target == "pod":
                    return "kubectl get pods -A -o wide"
                return f"kubectl get {target if target not in ('resource', 'unknown') else 'all'} -A -o wide"

            # 无具体资源名 → 先做诊断查询
            if target == "deployment":
                return "kubectl get deployment -A -o wide"
            if target == "pod":
                return "kubectl get pods -A -o wide"
            return "kubectl get all -A"
        except Exception:
            return "kubectl get all -A"

    @staticmethod
    def _canonical_command(cmd: str) -> str:
        """规范化命令字符串（去空白、转小写），用于比较命令是否重复"""
        return " ".join(str(cmd or "").split()).strip().lower()

    @staticmethod
    def _outcome_fingerprint(execution_result: dict) -> str:
        """执行结果指纹：根据是否成功 + 输出内容判定结果是否相同"""
        import hashlib
        data = "{}|{}|{}".format(
            execution_result.get("success"),
            execution_result.get("result"),
            execution_result.get("error"),
        )
        return hashlib.md5(data.encode("utf-8", "ignore")).hexdigest()

    async def _generate_fix_options(
        self,
        task_plan: dict,
        execution_result: dict,
        observation: dict,
        all_results: list,
        all_observations: list,
        iteration: int,
        memories: list = None,
    ) -> list:
        """
        当问题未解决时，用 LLM 生成多个修复选项
        
        返回: [{"description": "...", "command": "...", "confidence": 0.0-1.0}, ...]
        """
        import json as _json
        
        # 构建历史上下文
        history_text = ""
        for i, (res, obs) in enumerate(zip(all_results, all_observations)):
            history_text += f"""
第 {i+1} 轮:
  命令: {res.get('command', '')}
  输出: {str(res.get('result', ''))[:500]}
  观察: {obs.get('findings', '')}
  状态: {obs.get('status', 'unknown')}
"""
        
        prompt = f"""你是 Kubernetes 运维专家。当前问题尚未解决，请分析现状并生成下一步修复方案。

## 原始任务
{_json.dumps(task_plan, ensure_ascii=False)}

## 执行历史
{history_text}

## 当前观察
- 状态: {observation.get('status', 'unknown')}
- 发现: {observation.get('findings', '')}
- 详情: {observation.get('details', '')}

## 要求
请生成 1-3 个下一步修复方案（按推荐优先级排序）。每个方案包含：
- description: 方案描述（一句话）
- command: 要执行的 kubectl/系统命令
- confidence: 信心度 (0.0-1.0)

如果只有一个非常明确的方案且信心度 >= 0.8，只返回 1 个方案（系统会自动执行）。
如果有多个可能方案或不确定，返回 2-3 个方案让用户选择。

【重要】如果原始任务是“创建 Pod / 起 pod”(task_type=create、target=pod)，必须创建真正的 Pod：用 `kubectl run <名称> --image=<镜像>`(每个 Pod 一条命令，多个用 && 连接)，不要用 `kubectl create deployment`(那是 Deployment 不是 Pod)。用户未指定镜像时默认 nginx:latest。

输出格式（严格 JSON 数组）：
[
  {{
    "description": "方案描述",
    "command": "具体命令",
    "confidence": 0.9
  }}
]

只返回 JSON 数组，不要包含其他内容。"""

        # 注入用户偏好，让修复命令遵循用户偏好的工具
        if memories:
            _mem_lines = "\n".join([f"- {m.content}" for m in memories[:5]])
            prompt += ("\n\n用户偏好信息（来自长期记忆，生成命令时应遵循）：\n" + _mem_lines +
                       "\n提示：如涉及容器/镜像/CLI 命令，优先使用用户偏好的工具语法（例如用户偏好 nerdctl 时用 nerdctl 而不是 docker）。")

        try:
            from app.llm.client import get_client, get_current_model_name
            client = get_client()
            response = await client.chat.completions.create(
                model=get_current_model_name(),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2048,
                timeout=60.0,
            )
            content = response.choices[0].message.content.strip()
            
            # 解析 JSON
            import re
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                options = _json.loads(json_match.group())
                if isinstance(options, list) and len(options) > 0:
                    if str(task_plan.get("task_type", "")).lower() == "create" and str(task_plan.get("target", "")).lower() == "pod":
                        for _opt in options:
                            if isinstance(_opt, dict) and _opt.get("command"):
                                _opt["command"] = self._create_pod_command(_opt["command"], task_plan.get("namespace", ""))
                    return options
            
            print(f"[Workflow] 无法解析修复选项 JSON: {content[:300]}")
            return []
        except Exception as e:
            print(f"[Workflow] 生成修复选项失败: {e}")
            traceback.print_exc()
            return []

    def _has_pending_issues(self, observation: dict, task_plan: dict) -> bool:
        """
        检查是否还有待解决的问题
        即使 Observer 返回 healthy，如果用户意图是诊断/修复问题，
        且输出中包含异常状态（如 ImagePullBackOff, CrashLoopBackOff 等），
        也应该继续循环
        """
        # 检查用户意图是否是诊断/修复类
        task_type = task_plan.get("task_type", "")
        intent = task_plan.get("intent", "")
        description = task_plan.get("description", "")
        combined_intent = str(task_type).lower() + str(intent).lower() + str(description).lower()
        
        # 如果用户意图是创建问题/模拟故障，不要自动修复
        create_keywords = ["create_issue", "simulate", "制造", "创建问题", "模拟故障", "制造故障", "创建错误"]
        for kw in create_keywords:
            if kw.lower() in combined_intent:
                print(f"[Workflow] _has_pending_issues: 用户意图是创建/模拟问题，跳过自动修复")
                return False
        
        is_diagnostic = any(kw in combined_intent
                           for kw in ["diagnose", "诊断", "fix", "修复", "troubleshoot", "排查", "check", "检查"])
        
        if not is_diagnostic:
            return False
        
        # 检查 findings 和 details 中是否包含异常关键词
        findings = str(observation.get("findings", "")).lower()
        details = str(observation.get("details", "")).lower()
        status = str(observation.get("status", "")).lower()
        combined = findings + " " + details + " " + status
        
        error_keywords = [
            "imagepullbackoff", "crashloopbackoff", "errimagepull",
            "pending", "failed", "error", "oomkilled", "not ready",
            "0/1", "0/2", "createcontainerconfigerror", "invalidimage",
            "异常", "失败", "错误", "不可用",
        ]
        
        for kw in error_keywords:
            if kw.lower() in combined:
                print(f"[Workflow] _has_pending_issues: 检测到异常关键词 '{kw}'，继续循环")
                return True
        
        return False
