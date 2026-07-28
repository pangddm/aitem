"""
Reporter Agent — 报告者
职责：将整个流程的结果汇总为人类可读的自然语言报告
"""

from app.llm.agents.base_agent import BaseAgent


REPORTER_PROMPT = """
你是 Kubedoctor，一个友好的 Kubernetes 运维助手。

你的职责是将多 Agent 协作的流程结果，用自然、对话式的中文告诉用户。

回复要求：
1. 使用中文，像朋友聊天一样自然，不要使用"报告"、"操作概述"等正式格式
2. 【重要】必须包含关键数据，不要只给总结。例如用户问"容器状况"，你要列出 Pod 名称、状态、命名空间等具体信息
3. 如果有错误，给出可能的排查方向
4. 保持简洁，不啰嗦
5. 如果是理论知识问答，直接回答用户问题
6. 【重要】如果 validator_explanation 提示"需要先查询"或用户意图是操作但执行的是查询命令（如 kubectl get pods），
   你必须把查询结果展示给用户，然后明确引导用户指定具体要操作的资源名称。
   例如："当前有以下 Pod：\n- nginx-xxx  Running\n- nginx-yyy  Running\n\n你想重启哪一个？"
   不要直接替用户做决定，也不要只说"查询成功"就结束。
7. 【重要】如果有多轮执行历史，综合所有轮次的结果给出完整回答，不要只关注最后一轮
8. 【重要】回答中必须包含命令输出的关键数据，不要只给结论。例如：
   - 列出 Pod 时：给出 Pod 名称、状态、所在命名空间
   - 查看日志时：给出关键日志片段
   - 检查状态时：给出具体状态值

输出格式：
纯文本，不需要 JSON。直接输出对话内容。
"""


class Reporter(BaseAgent):
    """报告者：汇总结果，生成自然语言报告"""

    def __init__(self):
        super().__init__(name="reporter")

    def _build_context(self, memories: list = None, knowledge_context: str = "") -> str:
        """构建记忆和知识库上下文"""
        context_parts = []

        if knowledge_context:
            context_parts.append(
                f"以下是历史知识库案例，仅供参考：\n{knowledge_context}\n"
                f"规则：优先相信实时工具结果，不要照搬历史回答。"
            )

        if memories:
            memory_lines = []
            for m in memories:
                memory_lines.append(
                    f"- 类型: {m.type.value}\n"
                    f"  内容: {m.content}\n"
                    f"  摘要: {m.summary}\n"
                    f"  实体: {m.entities}"
                )
            context_parts.append(
                f"以下是历史长期记忆，仅作为辅助信息：\n"
                f"{chr(10).join(memory_lines)}\n"
                f"规则：不要盲目信任记忆，与实时结果冲突时以实时为准。"
            )

        return "\n\n".join(context_parts)

    async def report(self, task_plan: dict, risk_assessment: dict,
                     validation: dict, execution_result: dict,
                     observation: dict,
                     memories: list = None,
                     knowledge_context: str = "") -> dict:
        """
        汇总全流程结果，生成报告

        返回:
            {
                "reasoning": str,   # 思考链
                "answer": str,      # 最终回答
            }
        """
        extra_context = self._build_context(memories, knowledge_context)

        # 如果不需要执行（理论知识等），直接让 LLM 回答
        if not task_plan.get("requires_execution"):
            system_prompt = "你是 Kubernetes 运维专家，请用中文回答用户的问题。"
            if extra_context:
                system_prompt += f"\n\n{extra_context}"
            result = await self.think_with_reasoning(
                system_prompt=system_prompt,
                user_message=task_plan.get("description", ""),
            )
            return {"reasoning": result.get("reasoning", ""), "answer": result.get("content", "")}

        # 命令被拦截
        if validation.get("is_blocked"):
            answer = (
                f"操作已被拦截：{validation.get('explanation', '安全校验未通过')}\n"
                f"风险评估：{risk_assessment.get('reason', '')}\n"
                f"建议：{risk_assessment.get('suggestions', '请检查命令是否正确')}"
            )
            return {"reasoning": "", "answer": answer}

        # 执行失败
        if not execution_result.get("success"):
            answer = (
                f"命令执行失败\n"
                f"命令: {execution_result.get('command', '')}\n"
                f"错误: {execution_result.get('error', '未知错误')}\n"
                f"建议: 请检查网络连接、SSH 配置或集群状态"
            )
            return {"reasoning": "", "answer": answer}

        # 汇总成功结果
        user_intent = task_plan.get("description", "")
        command = execution_result.get("command", "")
        raw_output = execution_result.get("result", "")[:2000]
        status = observation.get("status", "unknown")
        findings = observation.get("findings", "")
        details = observation.get("details", "")
        risk = risk_assessment.get("risk_level", "")

        # 构建多轮执行历史
        import json as _json
        history_text = ""
        if all_execution_results and all_observations and len(all_execution_results) > 1:
            history_text = "\n## 执行历史（多轮）\n"
            for i, (res, obs) in enumerate(zip(all_execution_results, all_observations)):
                history_text += f"""
### 第 {i+1} 轮
- 命令: `{res.get('command', '')}`
- 输出: {str(res.get('result', ''))[:800]}
- 状态: {obs.get('status', 'unknown')}
- 发现: {obs.get('findings', '')}
"""
            history_text += "\n请综合以上所有轮次的执行结果，给出完整的诊断报告。\n"

        validator_note = validation.get("explanation", "")
        report_prompt = f"""
用户意图: {user_intent}
执行命令: {command}
validator_explanation: {validator_note}
风险等级: {risk}
命令输出: {raw_output}
状态: {status}
观察发现: {findings}
详细结果: {details}
{history_text}
"""

        system_prompt = REPORTER_PROMPT
        if extra_context:
            system_prompt += f"\n\n{extra_context}"

        result = await self.think_with_reasoning(
            system_prompt=system_prompt,
            user_message=report_prompt,
        )

        return {"reasoning": result.get("reasoning", ""), "answer": result.get("content", "")}

    async def report_stream(self, task_plan: dict, risk_assessment: dict,
                           validation: dict, execution_result: dict,
                           observation: dict,
                           memories: list = None,
                           knowledge_context: str = "",
                           all_execution_results: list = None,
                           all_observations: list = None):
        """
        流式输出报告，yield 字典事件

        yield 格式:
            {"type": "reasoning", "content": "..."}   # 思考链
            {"type": "content", "content": "..."}      # 正文
        """
        extra_context = self._build_context(memories, knowledge_context)

        # 如果不需要执行（理论知识等），直接流式回答
        if not task_plan.get("requires_execution"):
            system_prompt = "你是 Kubernetes 运维专家，请用中文回答用户的问题。"
            if extra_context:
                system_prompt += f"\n\n{extra_context}"
            has_content = False
            async for event in self.think_stream(
                system_prompt=system_prompt,
                user_message=task_plan.get("description", ""),
            ):
                if event.get("type") == "content" and event.get("content"):
                    has_content = True
                yield event
            # 如果 LLM 返回空内容，给出兜底提示
            if not has_content:
                yield {"type": "content", "content": "⚠️ AI 服务暂时不可用，请稍后重试。如果问题持续，请检查 LLM API 配置。"}
            return

        # 命令被拦截 — 直接输出文本，不走流式
        if validation.get("is_blocked"):
            text = (
                f"操作已被拦截：{validation.get('explanation', '安全校验未通过')}\n"
                f"风险评估：{risk_assessment.get('reason', '')}\n"
                f"建议：{risk_assessment.get('suggestions', '请检查命令是否正确')}"
            )
            yield {"type": "content", "content": text}
            return

        # 执行失败 — 同上
        if not execution_result.get("success"):
            text = (
                f"命令执行失败\n"
                f"命令: {execution_result.get('command', '')}\n"
                f"错误: {execution_result.get('error', '未知错误')}\n"
                f"建议: 请检查网络连接、SSH 配置或集群状态"
            )
            yield {"type": "content", "content": text}
            return

        # 汇总成功结果
        user_intent = task_plan.get("description", "")
        command = execution_result.get("command", "")
        raw_output = execution_result.get("result", "")[:2000]
        status = observation.get("status", "unknown")
        findings = observation.get("findings", "")
        details = observation.get("details", "")
        risk = risk_assessment.get("risk_level", "")

        # 构建多轮执行历史
        import json as _json
        history_text = ""
        if all_execution_results and all_observations and len(all_execution_results) > 1:
            history_text = "\n## 执行历史（多轮）\n"
            for i, (res, obs) in enumerate(zip(all_execution_results, all_observations)):
                history_text += f"""
### 第 {i+1} 轮
- 命令: `{res.get('command', '')}`
- 输出: {str(res.get('result', ''))[:800]}
- 状态: {obs.get('status', 'unknown')}
- 发现: {obs.get('findings', '')}
"""
            history_text += "\n请综合以上所有轮次的执行结果，给出完整的诊断报告。\n"

        validator_note = validation.get("explanation", "")
        report_prompt = f"""
用户意图: {user_intent}
执行命令: {command}
validator_explanation: {validator_note}
风险等级: {risk}
命令输出: {raw_output}
状态: {status}
观察发现: {findings}
详细结果: {details}
{history_text}
"""

        system_prompt = REPORTER_PROMPT
        if extra_context:
            system_prompt += f"\n\n{extra_context}"

        async for event in self.think_stream(
            system_prompt=system_prompt,
            user_message=report_prompt,
        ):
            yield event
