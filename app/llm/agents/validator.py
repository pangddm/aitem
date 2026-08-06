"""
Validator Agent — 命令校验者
职责：根据意图生成具体命令，并通过 check.py 安全校验
支持反馈循环：根据 Observer 的建议重新生成命令
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
7. 用户问"集群里有没有出故障的 Pod / 检查 Pod / 帮我看看有没有问题"这类诊断查询（通常未指定命名空间）→ 首条命令必须用 kubectl get pods -A -o wide（跨所有命名空间列出 Pod 以发现故障），不要用检查节点、kubelet 或节点代理的命令来回答 Pod 故障问题
8. 当用户明确点名要删除/清理/重启具体资源（即使未指定 namespace 或包含多个名称）时，必须生成可执行的 kubectl 命令，禁止只输出风险说明而把 command 留空。未指定 namespace 时可用 -n default。
9. 删除/重启多个资源时，可用 && 连接成一条命令，例如：kubectl delete deployment a -n default && kubectl delete deployment b -n default

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

意图: {"intent": "diagnose", "task_type": "get", "target": "pod", "resource_name": "", "namespace": ""}
输出: {"command": "kubectl get pods -A -o wide", "is_safe": true, "explanation": "跨所有命名空间列出 Pod，找出处于故障状态的 Pod（Pending/CrashLoopBackOff/ImagePullBackOff 等），后续再决定修复方案"}

意图: {"intent": "query", "task_type": "get", "target": "pod", "resource_name": "", "namespace": "default"}
输出: {"command": "kubectl get pods -n default -o wide", "is_safe": true, "explanation": "列出 default 命名空间下的全部 Pod，用于发现故障"}
"""

VALIDATOR_FEEDBACK_PROMPT = """
你是 Kubernetes 命令构建与校验专家。

上一次生成的命令执行后，Observer 发现结果不理想，需要你根据反馈重新生成命令。

规则：
1. 仔细分析 Observer 的反馈建议
2. 根据反馈调整命令策略
3. 如果上次命令是查询但没查到，尝试更精确的查询
4. 如果上次命令执行失败，分析原因并生成修正后的命令
5. 保持安全第一原则

输出格式（严格 JSON）：
{
  "command": "修正后的 kubectl 命令",
  "is_safe": true/false,
  "explanation": "修正说明"
}
"""


class Validator(BaseAgent):
    """命令校验者：生成命令 + 安全校验"""

    def __init__(self):
        super().__init__(name="validator")

    def _build_preference_hint(self, memories) -> str:
        """从长期记忆中提取用户对工具/CLI 的偏好，用于命令生成"""
        if not memories:
            return ""
        lines = "\n".join([f"- {m.content}" for m in memories[:5]])
        return (
            "\n\n用户偏好信息（来自长期记忆，生成命令时应遵循）：\n" + lines +
            "\n提示：如果任务涉及容器/镜像/CLI 相关命令，请优先使用用户偏好的工具语法。"
            "例如用户偏好 nerdctl 而不是 docker 时，容器相关命令使用 nerdctl 语法；"
            "kubectl 等集群命令不受影响。不要生成与用户明确偏好相悖的容器工具命令。"
        )

    async def generate_command(self, task_plan: dict, memories: list = None) -> dict:
        """
        仅生成命令（用于并行执行），不包含安全校验

        返回:
            {
                "reasoning": str,     # 思考链
                "command": str,       # 生成的命令
                "explanation": str,   # 命令说明
            }
        """
        system_prompt = VALIDATOR_PROMPT + self._build_preference_hint(memories)
        result = await self.think_json_with_reasoning(
            system_prompt=system_prompt,
            user_message=f"意图: {task_plan}",
        )

        reasoning = result.get("reasoning", "")
        data = result.get("data", {})

        return {
            "reasoning": reasoning,
            "command": data.get("command", ""),
            "explanation": data.get("explanation", ""),
        }

    async def generate_command_with_feedback(
        self,
        task_plan: dict,
        previous_command: str,
        execution_output: str,
        observation_feedback: str,
        memories: list = None,
    ) -> dict:
        """
        根据 Observer 反馈重新生成命令（反馈循环用）

        返回:
            {
                "reasoning": str,     # 思考链
                "command": str,       # 修正后的命令
                "explanation": str,   # 修正说明
            }
        """
        feedback_message = f"""
原始意图: {task_plan}
上一次命令: {previous_command}
执行输出: {execution_output[:1500]}
Observer 反馈: {observation_feedback}

请根据以上信息重新生成更合适的命令。
"""

        system_prompt = VALIDATOR_FEEDBACK_PROMPT + self._build_preference_hint(memories)
        result = await self.think_json_with_reasoning(
            system_prompt=system_prompt,
            user_message=feedback_message,
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
        # 测试模式下跳过安全校验
        from app.core.config import TEST_MODE
        if TEST_MODE:
            return {
                "command": command,
                "is_safe": True,
                "is_blocked": False,
                "explanation": "测试模式：跳过安全校验",
            }

        # critical 级别直接拦截：保留原命令，交由 workflow 弹确认窗让用户决定
        if risk_level == "critical":
            return {
                "command": command,
                "is_safe": False,
                "is_blocked": True,
                "explanation": "critical 级别风险，需用户确认后执行",
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