"""
Agent 工作流引擎
串联所有 Agent，完成从意图分析到结果报告的完整流程
支持并行执行和思考链推送
"""

import asyncio
import traceback

from app.llm.agents.orchestrator import Orchestrator
from app.llm.agents.risk_assessor import RiskAssessor
from app.llm.agents.validator import Validator
from app.llm.agents.executor import Executor
from app.llm.agents.observer import Observer
from app.llm.agents.reporter import Reporter


class AgentWorkflow:
    """多 Agent 工作流引擎"""

    def __init__(self):
        self.orchestrator = Orchestrator()
        self.risk_assessor = RiskAssessor()
        self.validator = Validator()
        self.executor = Executor()
        self.observer = Observer()
        self.reporter = Reporter()

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
        cmd_task = self.validator.generate_command(task_plan)

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

        # 4. Executor — 执行命令
        execution_result = await self.executor.execute(validation["command"])
        print(f"[Workflow] 执行结果: {execution_result.get('success')}")

        # 5. Observer — 观察验证
        obs_result = await self.observer.observe(task_plan, execution_result)
        observation = obs_result["observation"]
        if obs_result["reasoning"]:
            all_reasoning.append(f"[结果观察] {obs_result['reasoning']}")
        print(f"[Workflow] 观察结果: {observation.get('status')}")

        # 6. Reporter — 汇总报告
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

    async def run_stream(
        self,
        user_id: str,
        user_message: str,
        memories: list = None,
        knowledge_context: str = "",
    ):
        """
        运行工作流（流式），yield SSE 事件
        支持并行执行和思考链推送

        事件类型:
            {"type": "reasoning", "agent": "...", "content": "..."}  # 各 Agent 思考链
            {"type": "task_plan", "content": {...}}
            {"type": "risk_assessment", "content": {...}}
            {"type": "validation", "content": {...}}
            {"type": "tool_call", "tool": "...", "command": "..."}
            {"type": "tool_result", "tool": "...", "result": "..."}
            {"type": "observation", "content": {...}}
            {"type": "answer_reasoning", "content": "..."}           # Reporter 思考链
            {"type": "answer_chunk", "content": "..."}              # Reporter 正文
            {"type": "done"}
            {"type": "error", "content": "..."}
        """
        print(f"[Workflow Stream] 用户 {user_id} 发起请求: {user_message}")

        try:
            # 1. Orchestrator
            print("[Workflow Stream] 步骤1: Orchestrator 分析意图...")
            orc_result = await self.orchestrator.analyze(user_message)
            task_plan = orc_result["task_plan"]
            print(f"[Workflow Stream] task_plan: {task_plan}")
            if orc_result["reasoning"]:
                yield {"type": "reasoning", "agent": "orchestrator", "content": orc_result["reasoning"]}
            yield {"type": "task_plan", "content": task_plan}

            # 不需要执行
            if not task_plan.get("requires_execution"):
                async for event in self.reporter.report_stream(
                    task_plan, {}, {}, {}, {},
                    memories=memories, knowledge_context=knowledge_context,
                ):
                    if event["type"] == "reasoning":
                        yield {"type": "answer_reasoning", "content": event["content"]}
                    else:
                        yield {"type": "answer_chunk", "content": event["content"]}
                yield {"type": "done"}
                return

            # 2. 并行执行：Risk Assessor + Validator 命令生成
            print("[Workflow Stream] 步骤2: 并行执行风险评估 + 命令生成...")
            risk_task = self.risk_assessor.assess(task_plan)
            cmd_task = self.validator.generate_command(task_plan)

            risk_result, cmd_result = await asyncio.gather(risk_task, cmd_task)
            print(f"[Workflow Stream] risk_result keys: {list(risk_result.keys())}")
            print(f"[Workflow Stream] cmd_result: {cmd_result}")

            risk_assessment = risk_result["risk_assessment"]
            if risk_result["reasoning"]:
                yield {"type": "reasoning", "agent": "risk_assessor", "content": risk_result["reasoning"]}
            yield {"type": "risk_assessment", "content": risk_assessment}

            if cmd_result["reasoning"]:
                yield {"type": "reasoning", "agent": "validator", "content": cmd_result["reasoning"]}

            # 3. 安全校验（纯同步）
            validation = self.validator.check_safety(
                cmd_result.get("command", ""),
                risk_assessment.get("risk_level", ""),
            )
            validation["explanation"] = cmd_result.get("explanation", validation.get("explanation", ""))
            yield {"type": "validation", "content": validation}

            # 命令被拦截
            if validation.get("is_blocked"):
                async for event in self.reporter.report_stream(
                    task_plan, risk_assessment, validation, {}, {},
                    memories=memories, knowledge_context=knowledge_context,
                ):
                    if event["type"] == "reasoning":
                        yield {"type": "answer_reasoning", "content": event["content"]}
                    else:
                        yield {"type": "answer_chunk", "content": event["content"]}
                yield {"type": "done"}
                return

            # 4. Executor
            command = validation.get("command", "")
            print(f"[Workflow Stream] 步骤4: 执行命令: {command}")
            yield {"type": "tool_call", "tool": "execute_command", "command": command}

            execution_result = await self.executor.execute(command)
            print(f"[Workflow Stream] 执行结果 success={execution_result.get('success')}")
            print(f"[Workflow Stream] 执行结果 output={str(execution_result.get('result', ''))[:300]}")
            yield {
                "type": "tool_result",
                "tool": "execute_command",
                "result": str(execution_result.get("result", ""))[:500],
            }

            # 5. Observer
            obs_result = await self.observer.observe(task_plan, execution_result)
            if obs_result["reasoning"]:
                yield {"type": "reasoning", "agent": "observer", "content": obs_result["reasoning"]}
            yield {"type": "observation", "content": obs_result["observation"]}

            # 6. Reporter — 流式输出
            async for event in self.reporter.report_stream(
                task_plan, risk_assessment, validation,
                execution_result, obs_result["observation"],
                memories=memories, knowledge_context=knowledge_context,
            ):
                if event["type"] == "reasoning":
                    yield {"type": "answer_reasoning", "content": event["content"]}
                else:
                    yield {"type": "answer_chunk", "content": event["content"]}

            yield {"type": "done"}

        except Exception as e:
            print(f"[Workflow Stream] 异常: {e}")
            traceback.print_exc()
            yield {"type": "error", "content": str(e)}