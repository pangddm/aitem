from app.llm.agents.base_agent import BaseAgent
from app.llm.agents.orchestrator import Orchestrator
from app.llm.agents.risk_assessor import RiskAssessor
from app.llm.agents.validator import Validator
from app.llm.agents.executor import Executor
from app.llm.agents.observer import Observer
from app.llm.agents.reporter import Reporter
from app.llm.agents.command_rewriter import CommandRewriter
from app.llm.agents.workflow import AgentWorkflow

# 全局字典：存储待确认的命令（供 API 层设置用户选择）
_pending_confirmations = {}
