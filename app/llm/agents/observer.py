"""
Observer Agent — 观察者
职责：执行命令后检查系统状态，判断操作是否达到预期效果
"""

from app.llm.agents.base_agent import BaseAgent


OBSERVER_PROMPT = """
你是 Kubernetes 运维观察专家。

你的职责是根据用户意图、执行的命令和输出结果，判断操作是否成功。

判断依据：
1. 命令输出是否包含错误信息（Error, Failed, NotFound, CrashLoopBackOff 等）
2. 命令输出是否符合预期（如 Pod 状态为 Running，Deployment 可用副本数正常）
3. 如果是查询操作，判断是否返回了有效数据

输出格式（严格 JSON）：
{
  "success": true/false,
  "status": "healthy | warning | error | unknown",
  "findings": "观察发现摘要",
  "details": "详细观察结果"
}

示例：
命令: kubectl get pods -n default
输出: NAME READY STATUS RESTARTS AGE\nnginx-xxx 1/1 Running 0 5m

结果: {"success": true, "status": "healthy", "findings": "1 个 Pod 运行正常", "details": "nginx-xxx 状态为 Running，1/1 Ready"}

命令: kubectl get pods -n prod
输出: Error from server (NotFound): namespaces "prod" not found

结果: {"success": false, "status": "error", "findings": "命名空间 prod 不存在", "details": "服务器返回 NotFound 错误"}
"""


class Observer(BaseAgent):
    """观察者：验证执行结果"""

    def __init__(self):
        super().__init__(name="observer")

    async def observe(self, task_plan: dict, execution_result: dict) -> dict:
        """
        分析执行结果，判断操作是否成功

        返回:
            {
                "reasoning": str,    # 思考链
                "observation": dict, # 观察结果
            }
        """
        # 如果执行本身就失败了，直接返回失败
        if not execution_result.get("success"):
            return {
                "reasoning": "",
                "observation": {
                    "success": False,
                    "status": "error",
                    "findings": "命令执行失败",
                    "details": execution_result.get("error", "未知错误"),
                },
            }

        # 调用 LLM 分析结果
        result = await self.think_json_with_reasoning(
            system_prompt=OBSERVER_PROMPT,
            user_message=(
                f"用户意图: {task_plan}\n"
                f"执行命令: {execution_result.get('command', '')}\n"
                f"命令输出: {execution_result.get('result', '')[:2000]}"
            ),
        )

        reasoning = result.get("reasoning", "")
        observation = result.get("data", {})

        if not observation:
            observation = {
                "success": True,
                "status": "unknown",
                "findings": "无法解析执行结果",
                "details": execution_result.get("result", "")[:500],
            }

        return {"reasoning": reasoning, "observation": observation}