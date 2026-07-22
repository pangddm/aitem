"""
Validator Agent — 命令校验者
职责：根据意图生成具体命令，并通过 check.py 安全校验
"""

from app.llm.agents.base_agent import BaseAgent
from app.schemas.check import is_safe_command


VALIDATOR_PROMPT = """
你是 Kubernetes 命令构建与校验专家。

根据用户意图，生成具体的 kubectl 命令。

命令生成规则：
1. 只生成 kubectl 命令，不要生成 shell 命令
2. 如果有指定 namespace，加上 -n 参数
3. 如果是查看日志，使用 kubectl logs
4. 如果是重启操作（restart），优先使用 kubectl rollout restart
5. 命令必须安全，不能包含 rm, delete all 等危险操作
6. 允许使用 kubectl delete pod <pod-name> 来重启单个 Pod（K8s 控制器会自动重建）

重要：处理资源名称缺失的情况
- 如果用户意图是操作（operate）但 resource_name 为空，必须生成查询命令先获取资源列表
- 例如：用户想重启 Pod 但没指定名称 → 生成 kubectl get pods 先查询
- 在 explanation 中说明：需要先查询资源列表，确认具体资源名称后再执行操作

Kubernetes 操作转换规则：
- restart pod（无名称）→ kubectl get pods -n <namespace>（先查询）
- restart deployment → kubectl rollout restart deployment <name> -n <namespace>
- restart pod（有名称）→ kubectl delete pod <name> -n <namespace>（控制器会重建）
- scale deployment → kubectl scale deployment <name> --replicas=<n> -n <namespace>
- get/describe → 直接生成对应 kubectl 命令

输出格式（严格 JSON）：
{
  "command": "完整的 kubectl 命令",
  "is_safe": true/false,
  "explanation": "命令说明"
}

示例：
意图: {"intent": "query", "task_type": "get", "target": "pod", "namespace": "default"}
输出: {"command": "kubectl get pods -n default", "is_safe": true, "explanation": "查看 default 命名空间的 Pod"}

意图: {"intent": "operate", "task_type": "restart", "target": "deployment", "resource_name": "nginx", "namespace": "prod"}
输出: {"command": "kubectl rollout restart deployment nginx -n prod", "is_safe": true, "explanation": "重启 prod 命名空间的 nginx deployment"}

意图: {"intent": "operate", "task_type": "restart", "target": "pod", "resource_name": "", "namespace": "default"}
输出: {"command": "kubectl get pods -n default", "is_safe": true, "explanation": "需要先查询 Pod 列表，确认具体 Pod 名称后再执行重启操作"}

意图: {"intent": "operate", "task_type": "restart", "target": "pod", "resource_name": "nginx-xxx", "namespace": "default"}
输出: {"command": "kubectl delete pod nginx-xxx -n default", "is_safe": true, "explanation": "删除 default 命名空间的 nginx-xxx Pod，控制器会自动重建"}
"""


class Validator(BaseAgent):
    """命令校验者：生成命令 + 安全校验"""

    def __init__(self):
        super().__init__(name="validator")

    async def generate_command(self, task_plan: dict) -> dict:
        """
        仅生成命令（用于并行执行），不包含安全校验

        返回:
            {
                "reasoning": str,     # 思考链
                "command": str,       # 生成的命令
                "explanation": str,   # 命令说明
            }
        """
        result = await self.think_json_with_reasoning(
            system_prompt=VALIDATOR_PROMPT,
            user_message=f"意图: {task_plan}",
        )

        reasoning = result.get("reasoning", "")
        data = result.get("data", {})

        return {
            "reasoning": reasoning,
            "command": data.get("command", ""),
            "explanation": data.get("explanation", ""),
        }

    def check_safety(self, command: str, risk_level: str) -> dict:
        """
        安全校验（纯同步，不调用 LLM）

        返回:
            {
                "command": str,
                "is_safe": bool,
                "is_blocked": bool,
                "explanation": str,
            }
        """
        # critical 级别直接拦截
        if risk_level == "critical":
            return {
                "command": "",
                "is_safe": False,
                "is_blocked": True,
                "explanation": "critical 级别风险，操作被拦截",
            }

        if not command:
            return {
                "command": "",
                "is_safe": False,
                "is_blocked": True,
                "explanation": "无法生成有效命令",
            }

        is_safe = is_safe_command(command)

        return {
            "command": command,
            "is_safe": is_safe,
            "is_blocked": not is_safe,
            "explanation": "安全校验通过" if is_safe else "安全校验未通过",
        }

    async def validate(self, task_plan: dict, risk_assessment: dict) -> dict:
        """
        完整校验流程（生成命令 + 安全校验），用于非并行模式

        返回:
            {
                "reasoning": str,     # 思考链
                "command": str,       # 生成的命令
                "is_safe": bool,      # 是否通过安全校验
                "is_blocked": bool,   # 是否被拦截
                "explanation": str,   # 命令说明
            }
        """
        # critical 级别直接拦截
        if risk_assessment.get("risk_level") == "critical":
            return {
                "reasoning": "",
                "command": "",
                "is_safe": False,
                "is_blocked": True,
                "explanation": f"操作被拦截：{risk_assessment.get('reason', 'critical 级别风险')}",
            }

        # 调用 LLM 生成命令
        gen_result = await self.generate_command(task_plan)

        # 安全校验
        safety = self.check_safety(gen_result["command"], risk_assessment.get("risk_level", ""))

        return {
            "reasoning": gen_result["reasoning"],
            "command": safety["command"],
            "is_safe": safety["is_safe"],
            "is_blocked": safety["is_blocked"],
            "explanation": gen_result["explanation"],
        }