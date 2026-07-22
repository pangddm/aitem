"""
Risk Assessor Agent — 风险评估者
职责：评估操作的风险等级，决定是否需要人工确认
"""

from app.llm.agents.base_agent import BaseAgent


RISK_ASSESSOR_PROMPT = """
你是 Kubernetes 安全风险评估专家。

根据用户的操作意图，评估风险等级。

风险等级定义：
- read_only: 只读操作（get, describe, logs），无风险
- safe_write: 安全写操作（apply, create），低风险
- dangerous: 危险操作（delete, restart, scale down），高风险
- critical: 极其危险操作（delete all, drain node, remove 集群节点），严禁执行

输出格式（严格 JSON）：
{
  "risk_level": "read_only | safe_write | dangerous | critical",
  "requires_confirm": true/false,
  "reason": "风险评估理由",
  "suggestions": "建议或替代方案"
}

示例：
操作: {"intent": "query", "task_type": "get", "target": "pod"}
输出: {"risk_level": "read_only", "requires_confirm": false, "reason": "只读查询操作", "suggestions": ""}

操作: {"intent": "operate", "task_type": "delete", "target": "pod", "resource_name": "nginx-xxx"}
输出: {"risk_level": "dangerous", "requires_confirm": true, "reason": "删除 Pod 会导致服务中断", "suggestions": "建议先确认 Pod 是否属于 Deployment 管理"}
"""


class RiskAssessor(BaseAgent):
    """风险评估者：评估操作风险等级"""

    def __init__(self):
        super().__init__(name="risk_assessor")

    async def assess(self, task_plan: dict) -> dict:
        """
        评估任务风险，返回包含 risk_assessment 和 reasoning 的字典
        
        返回:
            {
                "reasoning": str,          # 思考链
                "risk_assessment": dict,   # 风险评估结果
            }
        """
        result = await self.think_json_with_reasoning(
            system_prompt=RISK_ASSESSOR_PROMPT,
            user_message=f"操作意图: {task_plan}",
        )

        reasoning = result.get("reasoning", "")
        risk_assessment = result.get("data", {})

        if not risk_assessment:
            risk_assessment = {
                "risk_level": "dangerous",
                "requires_confirm": True,
                "reason": "无法评估风险，默认按高风险处理",
                "suggestions": "",
            }

        return {"reasoning": reasoning, "risk_assessment": risk_assessment}