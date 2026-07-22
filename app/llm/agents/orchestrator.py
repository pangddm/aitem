"""
Orchestrator Agent — 编排者
职责：解析用户意图，拆解任务，协调下游 Agent
"""

from app.llm.agents.base_agent import BaseAgent


ORCHESTRATOR_PROMPT = """
你是 Kubernetes 运维编排专家。

你的职责是分析用户意图，拆解任务，并输出结构化的任务计划。

重要：仔细提取命名空间和资源名称。用户可能用以下格式引用资源：
- "default/nginx-xxx" → namespace: "default", resource_name: "nginx-xxx"
- "prod/redis-master-0" → namespace: "prod", resource_name: "redis-master-0"

输出格式（严格 JSON）：
{
  "intent": "query | operate | diagnose",
  "task_type": "get | delete | create | apply | restart | logs | describe | exec | scale | other",
  "target": "pod | deployment | service | node | namespace | event | log | resource | unknown",
  "resource_name": "资源名称，如 nginx-xxx，没有则为空",
  "namespace": "命名空间，未指定则为空",
  "description": "对用户意图的自然语言描述",
  "requires_execution": true/false
}

示例：
用户: "查看所有 Pod"
输出: {"intent": "query", "task_type": "get", "target": "pod", "resource_name": "", "namespace": "", "description": "查看所有 Pod", "requires_execution": true}

用户: "重启 nginx 服务"
输出: {"intent": "operate", "task_type": "restart", "target": "deployment", "resource_name": "nginx", "namespace": "", "description": "重启 nginx deployment", "requires_execution": true}

用户: "我要重启这个default/nginx-56fcf95486-8t6qw"
输出: {"intent": "operate", "task_type": "restart", "target": "pod", "resource_name": "nginx-56fcf95486-8t6qw", "namespace": "default", "description": "重启 default 命名空间的 nginx-56fcf95486-8t6qw Pod", "requires_execution": true}

用户: "什么是 Deployment"
输出: {"intent": "query", "task_type": "other", "target": "unknown", "resource_name": "", "namespace": "", "description": "询问 Kubernetes 理论知识", "requires_execution": false}
"""


class Orchestrator(BaseAgent):
    """编排者：解析意图，拆解任务"""

    def __init__(self):
        super().__init__(name="orchestrator")

    async def analyze(self, user_message: str) -> dict:
        """
        分析用户意图，返回包含 task_plan 和 reasoning 的字典
        
        返回:
            {
                "reasoning": str,    # 思考链
                "task_plan": dict,   # 任务计划
            }
        """
        result = await self.think_json_with_reasoning(
            system_prompt=ORCHESTRATOR_PROMPT,
            user_message=user_message,
        )

        reasoning = result.get("reasoning", "")
        task_plan = result.get("data", {})

        # 默认值兜底
        if not task_plan:
            task_plan = {
                "intent": "query",
                "task_type": "other",
                "target": "unknown",
                "resource_name": "",
                "namespace": "",
                "description": user_message,
                "requires_execution": False,
            }

        return {"reasoning": reasoning, "task_plan": task_plan}
