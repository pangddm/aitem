"""
LangGraph 工作流引擎
用 StateGraph 替代原有的 AgentWorkflow，保留所有现有 Agent 类

工作流图结构:

    [START]
        │
    command_rewriter ── 重写用户模糊问题
        │
    orchestrator ── 分析意图
        │
    ┌───┤
    │   │ (requires_execution=false)
    │   └──→ reporter ──→ [END]
    │
    risk_assessor ──→ validator (并行)
        │
    check_safety ── 安全校验
        │
    ┌───┤
    │   │ (is_blocked)
    │   └──→ reporter ──→ [END]
    │
    executor ── 执行命令
        │
    observer ── 观察结果
        │
    ┌───┤
    │   │ (needs_retry && loop < MAX)
    │   └──→ validator (反馈循环)
    │
    ┌───┤
    │   │ (has_pending_issues)
    │   └──→ fix_generator ──→ executor (自动修复循环)
    │
    reporter ──→ [END]
"""

from __future__ import annotations

import asyncio
import os
import traceback
from typing import Annotated, Any, AsyncGenerator, Literal, Optional

from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict

from app.llm.agents.orchestrator import Orchestrator
from app.llm.agents.risk_assessor import RiskAssessor
from app.llm.agents.validator import Validator
from app.llm.agents.executor import Executor
from app.llm.agents.observer import Observer
from app.llm.agents.reporter import Reporter
from app.llm.agents.command_rewriter import CommandRewriter
from app.llm.client import get_current_model_display, get_model_status
from app.core.logger import get_logger

logger = get_logger(__name__)

MAX_RETRY_LOOPS = 2
MAX_FIX_ITERATIONS = int(os.getenv("MAX_AGENT_ITERATIONS", "10"))


# ==========================================================
# State 定义
# ==========================================================

class AgentState(TypedDict):
    """LangGraph 工作流状态"""
    # 输入
    user_id: str
    user_message: str
    rewritten_message: str
    conversation_history: list | None
    memories: list | None
    knowledge_context: str
    host: str | None
    port: int | None
    username: str | None
    password: str | None

    # 中间结果
    task_plan: dict
    risk_assessment: dict
    validation: dict
    execution_result: dict
    observation: dict

    # 多轮执行历史
    all_execution_results: list
    all_observations: list
    iteration: int

    # 修复方案
    fix_options: list
    chosen_fix_index: int | None

    # 最终输出
    answer: str
    reasoning: list[str]

    # 流式事件队列（用于 SSE 推送）
    events: list[dict]

    # 内部标记
    _has_fix: bool
    _waiting_for_choice: bool  # 是否正在等待用户选择修复方案


# ==========================================================
# Node 函数
# ==========================================================

# 全局 Agent 实例（单例）
_orchestrator = Orchestrator()
_risk_assessor = RiskAssessor()
_validator = Validator()
_executor = Executor()
_observer = Observer()
_reporter = Reporter()
_command_rewriter = CommandRewriter()


async def command_rewriter_node(state: AgentState) -> dict:
    """重写用户模糊问题"""
    events = []
    events.append({
        "type": "workflow_status", "stage": "rewriter",
        "message": "正在理解您的问题..."
    })

    try:
        rewrite_result = await _command_rewriter.rewrite(
            state["user_message"],
            conversation_history=state.get("conversation_history"),
        )
        rewritten = rewrite_result.get("rewritten", state["user_message"])

        if rewrite_result.get("reasoning"):
            events.append({
                "type": "reasoning", "agent": "command_rewriter",
                "content": rewrite_result["reasoning"],
            })

        if rewritten != state["user_message"]:
            events.append({
                "type": "command_rewritten",
                "original": state["user_message"],
                "rewritten": rewritten,
                "key_entities": rewrite_result.get("key_entities", {}),
            })
    except Exception as e:
        logger.error("CommandRewriter 失败: %s", e, exc_info=True)
        rewritten = state["user_message"]

    return {
        "rewritten_message": rewritten,
        "events": events,
    }


async def orchestrator_node(state: AgentState) -> dict:
    """分析用户意图"""
    events = []
    events.append({
        "type": "workflow_status", "stage": "orchestrator",
        "message": "正在分析意图..."
    })

    try:
        orc_result = await _orchestrator.analyze(
            state["rewritten_message"],
            conversation_history=state.get("conversation_history"),
        )
        task_plan = orc_result.get("task_plan", {})

        if orc_result.get("reasoning"):
            events.append({
                "type": "reasoning", "agent": "orchestrator",
                "content": orc_result["reasoning"],
            })
        events.append({"type": "task_plan", "content": task_plan})
    except Exception as e:
        logger.error("Orchestrator 失败: %s", e, exc_info=True)
        task_plan = {
            "intent": "query", "task_type": "other",
            "target": "unknown", "resource_name": "",
            "namespace": "", "description": state["rewritten_message"],
            "requires_execution": False,
        }
        events.append({"type": "error", "content": f"意图分析失败: {e}"})

    return {"task_plan": task_plan, "events": events}


def should_execute(state: AgentState) -> Literal["reporter", "parallel"]:
    """判断是否需要执行命令"""
    task_plan = state.get("task_plan", {})
    if not task_plan.get("requires_execution"):
        return "reporter"
    return "parallel"


async def risk_assessor_node(state: AgentState) -> dict:
    """风险评估"""
    events = []
    try:
        risk_result = await _risk_assessor.assess(state["task_plan"])
        risk_assessment = risk_result.get("risk_assessment", {})
        if risk_result.get("reasoning"):
            events.append({
                "type": "reasoning", "agent": "risk_assessor",
                "content": risk_result["reasoning"],
            })
        events.append({"type": "risk_assessment", "content": risk_assessment})
    except Exception as e:
        logger.error("RiskAssessor 失败: %s", e, exc_info=True)
        risk_assessment = {
            "risk_level": "unknown", "reason": str(e),
            "suggestions": "", "requires_confirm": False,
        }

    return {"risk_assessment": risk_assessment, "events": events}


async def validator_node(state: AgentState) -> dict:
    """生成命令"""
    events = []
    try:
        cmd_result = await _validator.generate_command(state["task_plan"])
        if cmd_result.get("reasoning"):
            events.append({
                "type": "reasoning", "agent": "validator",
                "content": cmd_result["reasoning"],
            })

        # 安全校验
        validation = _validator.check_safety(
            cmd_result.get("command", ""),
            state["risk_assessment"].get("risk_level", ""),
        )
        validation["explanation"] = cmd_result.get(
            "explanation", validation.get("explanation", "")
        )
        validation["command"] = cmd_result.get("command", "")
        events.append({"type": "validation", "content": validation})
    except Exception as e:
        logger.error("Validator 失败: %s", e, exc_info=True)
        validation = {
            "command": "", "is_blocked": True,
            "explanation": f"命令生成失败: {e}",
        }

    return {"validation": validation, "events": events}


def check_safety(state: AgentState) -> Literal["reporter", "executor"]:
    """安全校验路由"""
    validation = state.get("validation", {})
    risk_assessment = state.get("risk_assessment", {})
    risk_level = risk_assessment.get("risk_level", "")

    if validation.get("is_blocked"):
        # critical 级别风险才拦截，其他风险级别允许执行
        if risk_level == "critical":
            return "reporter"
        # dangerous 或更低风险，允许执行
        return "executor"
    return "executor"


async def executor_node(state: AgentState) -> dict:
    """执行命令"""
    events = []
    command = state["validation"].get("command", "")
    iteration = state.get("iteration", 0) + 1

    events.append({
        "type": "workflow_status", "stage": "executor",
        "message": f"正在执行命令... (第{iteration}轮)",
    })
    events.append({
        "type": "tool_call", "tool": "execute_command", "command": command,
    })

    try:
        execution_result = await asyncio.wait_for(
            _executor.execute(
                command,
                host=state.get("host"),
                port=state.get("port"),
                username=state.get("username"),
                password=state.get("password"),
            ),
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        execution_result = {
            "command": command, "success": False,
            "result": "", "error": "命令执行超时（30秒）",
        }
    except Exception as e:
        execution_result = {
            "command": command, "success": False,
            "result": "", "error": str(e),
        }

    events.append({
        "type": "tool_result", "tool": "execute_command",
        "command": command,
        "result": str(execution_result.get("result", ""))[:500],
        "success": execution_result.get("success", False),
    })

    return {
        "execution_result": execution_result,
        "iteration": iteration,
        "events": events,
    }


async def observer_node(state: AgentState) -> dict:
    """观察执行结果"""
    events = []
    events.append({
        "type": "workflow_status", "stage": "observer",
        "message": "正在观察结果...",
    })

    try:
        obs_result = await _observer.observe(
            state["task_plan"], state["execution_result"],
        )
        observation = obs_result.get("observation", {})
        if obs_result.get("reasoning"):
            events.append({
                "type": "reasoning", "agent": "observer",
                "content": obs_result["reasoning"],
            })
        events.append({"type": "observation", "content": observation})
    except Exception as e:
        logger.error("Observer 失败: %s", e, exc_info=True)
        observation = {
            "success": True, "status": "unknown",
            "findings": str(e), "details": "",
            "needs_retry": False, "retry_suggestion": "",
        }

    # 更新执行历史
    all_results = state.get("all_execution_results", []) + [state["execution_result"]]
    all_obs = state.get("all_observations", []) + [observation]

    return {
        "observation": observation,
        "all_execution_results": all_results,
        "all_observations": all_obs,
        "events": events,
    }


def should_retry(state: AgentState) -> Literal["validator", "fix_generator", "reporter"]:
    """判断是否需要重试命令"""
    observation = state.get("observation", {})
    iteration = state.get("iteration", 0)
    task_plan = state.get("task_plan", {})
    execution_result = state.get("execution_result", {})

    # 查询类请求（get/logs/describe）执行一次就结束，不重试也不修复
    if task_plan.get("intent") == "query":
        return "reporter"

    # 如果执行成功且状态健康，直接报告
    if observation.get("success") and observation.get("status") in ("healthy", "warning"):
        # 但需要检查是否有待解决的问题（异常 Pod）
        if _has_pending_issues(observation, task_plan):
            logger.info("[should_retry] 检测到待解决问题，进入 fix_generator")
            return "fix_generator"

        # 额外检查：即使 Observer 没有检测到异常，也检查原始执行结果
        # 防止 Observer 的 LLM 路径误判
        result_text = str(execution_result.get("result", "")).lower()
        error_statuses = [
            "crashloopbackoff", "imagepullbackoff", "errimagepull",
            "pending", "oomkilled", "createcontainerconfigerror",
            "invalidimage", "init:error", "init:crashloopbackoff",
        ]
        if any(kw in result_text for kw in error_statuses):
            logger.info("[should_retry] 执行结果中发现异常状态，进入 fix_generator")
            return "fix_generator"

        return "reporter"

    if observation.get("needs_retry") and iteration < MAX_RETRY_LOOPS:
        return "validator"
    return "fix_generator"


def has_pending_issues(state: AgentState) -> Literal["fix_generator", "reporter"]:
    """判断是否还有待解决的问题"""
    observation = state.get("observation", {})
    task_plan = state.get("task_plan", {})

    # 查询类请求直接报告，不进入修复循环
    if task_plan.get("intent") == "query":
        return "reporter"

    # 如果已经 healthy 且没有异常，直接报告
    if observation.get("status") == "healthy" and observation.get("success"):
        if not _has_pending_issues(observation, task_plan):
            return "reporter"

    # 检查是否达到最大迭代次数
    iteration = state.get("iteration", 0)
    if iteration >= MAX_FIX_ITERATIONS:
        return "reporter"

    return "fix_generator"


async def fix_generator_node(state: AgentState) -> dict:
    """
    生成修复方案
    - 如果只有一个明确方案且信心度高（>=0.8），自动执行
    - 如果有多个方案，发送 fix_options 事件让用户选择，然后结束到 reporter
      （用户选择后前端会发送新消息来执行命令）
    """
    events = []
    events.append({
        "type": "workflow_status", "stage": "planning_next",
        "message": "🔄 问题未解决，正在分析下一步...",
    })

    try:
        fix_options = await _generate_fix_options(
            task_plan=state["task_plan"],
            execution_result=state["execution_result"],
            observation=state["observation"],
            all_results=state.get("all_execution_results", []),
            all_observations=state.get("all_observations", []),
            iteration=state.get("iteration", 0),
        )
    except Exception as e:
        logger.error("生成修复方案失败: %s", e, exc_info=True)
        fix_options = []

    new_validation = dict(state.get("validation", {}))
    has_fix = False

    if fix_options:
        # 如果只有一个明确方案且信心度 >= 0.8，自动执行
        if len(fix_options) == 1 and fix_options[0].get("confidence", 0) >= 0.8:
            chosen = fix_options[0]
            new_validation["command"] = chosen.get("command", "")
            new_validation["explanation"] = chosen.get("description", "")
            has_fix = True
            events.append({
                "type": "auto_fix",
                "content": f"🤖 自动执行: {chosen.get('description', '')}",
            })
        else:
            # 多个方案或不确定 → 发送 fix_options 让用户选择
            options = []
            for i, opt in enumerate(fix_options[:5]):
                options.append({
                    "id": f"option_{i}",
                    "label": f"{'✅' if i == 0 else '💡'} {opt.get('description', f'方案 {i+1}')}",
                    "command": opt.get("command", ""),
                    "description": opt.get("description", ""),
                    "confidence": opt.get("confidence", 0),
                })

            # 添加"跳过"选项
            options.append({
                "id": "skip",
                "label": "⏭️ 跳过，直接生成报告",
                "command": "",
                "description": "跳过修复，直接生成报告",
                "confidence": 0,
            })

            events.append({
                "type": "fix_options",
                "message": "🔍 发现以下可能的解决方案，请选择一个：",
                "options": options,
                "observation_summary": observation.get("findings", ""),
            })

    return {
        "fix_options": fix_options,
        "validation": new_validation,
        "events": events,
        "_has_fix": has_fix,
        "_waiting_for_choice": False,
    }


def route_fix(state: AgentState) -> Literal["executor", "reporter"]:
    """根据修复方案路由"""
    fix_options = state.get("fix_options", [])
    has_fix = state.get("_has_fix", False)

    if not fix_options or not has_fix:
        return "reporter"

    # 有自动修复方案，继续执行
    return "executor"


async def reporter_node(state: AgentState) -> dict:
    """生成最终报告"""
    events = []
    events.append({
        "type": "workflow_status", "stage": "reporter",
        "message": "正在生成报告...",
    })

    task_plan = state.get("task_plan", {})
    risk_assessment = state.get("risk_assessment", {})
    validation = state.get("validation", {})
    execution_result = state.get("execution_result", {})
    observation = state.get("observation", {})

    try:
        rep_result = await _reporter.report(
            task_plan, risk_assessment, validation,
            execution_result, observation,
            memories=state.get("memories"),
            knowledge_context=state.get("knowledge_context", ""),
            all_execution_results=state.get("all_execution_results"),
            all_observations=state.get("all_observations"),
        )
        answer = rep_result.get("answer", "")
        if rep_result.get("reasoning"):
            events.append({
                "type": "answer_reasoning", "content": rep_result["reasoning"],
            })
    except Exception as e:
        logger.error("Reporter 失败: %s", e, exc_info=True)
        answer = f"⚠️ 报告生成失败: {e}"

    events.append({"type": "answer_chunk", "content": answer})
    events.append({"type": "done"})

    return {"answer": answer, "events": events}


# ==========================================================
# 辅助函数
# ==========================================================

def _has_pending_issues(observation: dict, task_plan: dict) -> bool:
    """检查是否还有待解决的问题"""
    task_type = task_plan.get("task_type", "")
    intent = task_plan.get("intent", "")
    description = task_plan.get("description", "")
    combined_intent = str(task_type).lower() + str(intent).lower() + str(description).lower()

    # 如果用户意图是创建问题/模拟故障，不要自动修复
    create_keywords = ["create_issue", "simulate", "制造", "创建问题", "模拟故障", "制造故障", "创建错误"]
    for kw in create_keywords:
        if kw.lower() in combined_intent:
            return False

    is_diagnostic = any(kw in combined_intent
                       for kw in ["diagnose", "诊断", "fix", "修复", "troubleshoot", "排查", "check", "检查",
                                  "处理", "解决", "repair", "修理", "help", "帮助"])
    if not is_diagnostic:
        return False

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
            return True
    return False


async def _generate_fix_options(
    task_plan: dict,
    execution_result: dict,
    observation: dict,
    all_results: list,
    all_observations: list,
    iteration: int,
) -> list:
    """用 LLM 生成修复方案"""
    import json as _json
    import re

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

输出格式（严格 JSON 数组）：
[
  {{
    "description": "方案描述",
    "command": "具体命令",
    "confidence": 0.9
  }}
]

只返回 JSON 数组，不要包含其他内容。"""

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

        json_match = re.search(r'\[[\s\S]*\]', content)
        if json_match:
            options = _json.loads(json_match.group())
            if isinstance(options, list) and len(options) > 0:
                return options

        logger.warning("无法解析修复选项 JSON: %s", content[:300])
        return []
    except Exception as e:
        logger.error("生成修复选项失败: %s", e, exc_info=True)
        return []


# ==========================================================
# 构建 StateGraph
# ==========================================================

def build_workflow() -> StateGraph:
    """构建 LangGraph 工作流"""
    workflow = StateGraph(AgentState)

    # 注册节点
    workflow.add_node("command_rewriter", command_rewriter_node)
    workflow.add_node("orchestrator", orchestrator_node)
    workflow.add_node("risk_assessor", risk_assessor_node)
    workflow.add_node("validator", validator_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("observer", observer_node)
    workflow.add_node("fix_generator", fix_generator_node)
    workflow.add_node("reporter", reporter_node)

    # 定义边
    workflow.set_entry_point("command_rewriter")
    workflow.add_edge("command_rewriter", "orchestrator")

    # 条件分支：是否需要执行
    workflow.add_conditional_edges(
        "orchestrator",
        should_execute,
        {
            "reporter": "reporter",
            "parallel": "risk_assessor",
        },
    )

    # 并行：risk_assessor → validator
    workflow.add_edge("risk_assessor", "validator")

    # 条件分支：安全校验
    workflow.add_conditional_edges(
        "validator",
        check_safety,
        {
            "reporter": "reporter",
            "executor": "executor",
        },
    )

    # 执行 → 观察
    workflow.add_edge("executor", "observer")

    # 条件分支：是否需要重试
    workflow.add_conditional_edges(
        "observer",
        should_retry,
        {
            "validator": "validator",       # 反馈循环
            "fix_generator": "fix_generator",
            "reporter": "reporter",         # 查询类请求直接报告
        },
    )

    # 条件分支：是否有待解决问题
    workflow.add_conditional_edges(
        "fix_generator",
        route_fix,
        {
            "executor": "executor",         # 自动修复循环
            "reporter": "reporter",
        },
    )

    # 报告 → 结束
    workflow.add_edge("reporter", END)

    return workflow


# ==========================================================
# 全局工作流实例
# ==========================================================

graph_workflow = build_workflow().compile()


# ==========================================================
# 流式执行入口
# ==========================================================

async def run_graph_stream(
    user_id: str,
    user_message: str,
    memories: list = None,
    knowledge_context: str = "",
    host: str = None,
    port: int = None,
    username: str = None,
    password: str = None,
    conversation_history: list = None,
) -> AsyncGenerator[dict, None]:
    """
    运行 LangGraph 工作流（流式），yield SSE 事件
    """
    logger.info("用户 %s 发起请求: %s", user_id, user_message)

    # 发送模型信息
    yield {
        "type": "model_info",
        "model": get_current_model_display(),
        "models": get_model_status(),
    }

    # 初始化状态
    initial_state: AgentState = {
        "user_id": user_id,
        "user_message": user_message,
        "rewritten_message": user_message,
        "conversation_history": conversation_history,
        "memories": memories,
        "knowledge_context": knowledge_context or "",
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "task_plan": {},
        "risk_assessment": {},
        "validation": {},
        "execution_result": {},
        "observation": {},
        "all_execution_results": [],
        "all_observations": [],
        "iteration": 0,
        "fix_options": [],
        "chosen_fix_index": None,
        "answer": "",
        "reasoning": [],
        "events": [],
        "_has_fix": False,
        "_waiting_for_choice": False,
    }

    try:
        # 使用 LangGraph 的流式执行
        async for event in graph_workflow.astream_events(
            initial_state,
            version="v2",
            config={"recursion_limit": 100},
        ):
            event_type = event.get("event", "")
            node = event.get("name", "")

            # 节点开始
            if event_type == "on_chain_start":
                if node in ("command_rewriter", "orchestrator", "risk_assessor",
                           "validator", "executor", "observer", "fix_generator", "reporter"):
                    yield {
                        "type": "node_start",
                        "node": node,
                    }

            # 节点结束 — 从 output 中提取 events
            elif event_type == "on_chain_end":
                if node in ("command_rewriter", "orchestrator", "risk_assessor",
                           "validator", "executor", "observer", "fix_generator", "reporter"):
                    data = event.get("data", {})
                    output = data.get("output", {})
                    if isinstance(output, dict):
                        node_events = output.get("events", [])
                        for evt in node_events:
                            yield evt

                    yield {
                        "type": "node_end",
                        "node": node,
                    }

    except Exception as e:
        logger.error("Graph Stream 异常: %s", e, exc_info=True)
        yield {"type": "error", "content": str(e)}
        yield {"type": "done"}


# ==========================================================
# 非流式执行入口（兼容旧接口）
# ==========================================================

async def run_graph(
    user_id: str,
    user_message: str,
    memories: list = None,
    knowledge_context: str = "",
    conversation_history: list = None,
) -> dict:
    """
    运行 LangGraph 工作流（非流式）
    """
    initial_state: AgentState = {
        "user_id": user_id,
        "user_message": user_message,
        "rewritten_message": user_message,
        "conversation_history": conversation_history,
        "memories": memories,
        "knowledge_context": knowledge_context or "",
        "host": None,
        "port": None,
        "username": None,
        "password": None,
        "task_plan": {},
        "risk_assessment": {},
        "validation": {},
        "execution_result": {},
        "observation": {},
        "all_execution_results": [],
        "all_observations": [],
        "iteration": 0,
        "fix_options": [],
        "chosen_fix_index": None,
        "answer": "",
        "reasoning": [],
        "events": [],
        "_has_fix": False,
        "_waiting_for_choice": False,
    }

    try:
        final_state = await graph_workflow.ainvoke(initial_state)
        return {
            "answer": final_state.get("answer", ""),
            "reasoning": "\n\n".join(final_state.get("reasoning", [])),
            "task_plan": final_state.get("task_plan", {}),
            "risk_assessment": final_state.get("risk_assessment", {}),
            "validation": final_state.get("validation", {}),
            "execution_result": final_state.get("execution_result", {}),
            "observation": final_state.get("observation", {}),
        }
    except Exception as e:
        logger.error("Graph 执行失败: %s", e, exc_info=True)
        return {
            "answer": f"⚠️ 工作流执行失败: {e}",
            "reasoning": "",
            "task_plan": {},
        }