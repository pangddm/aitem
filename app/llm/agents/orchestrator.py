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

requires_execution 规则：
- 查询集群状态（查看、显示、列出、检查 Pod/Node/Deployment 等）→ requires_execution: true
  （因为需要执行 kubectl 命令获取真实数据）
- 需要执行操作（重启、删除、创建、修改、扩容等）→ requires_execution: true
- 诊断问题（排查、修复、解决等）→ requires_execution: true
- 询问之前的对话/历史、回忆或确认（如"我上一个问题是什么"、"我之前问了什么"、"刚才那条命令是什么"、"我们聊过什么"、"这句话是什么意思"）→ requires_execution: false
  （这只是回顾/确认对话内容，不针对当前集群做任何查询或操作，绝不能执行任何命令）
- 理论知识、闲聊、解释概念（什么是、Kubernetes 是什么等）→ requires_execution: false

示例：
用户: "查看所有 Pod"
输出: {"intent": "query", "task_type": "get", "target": "pod", "resource_name": "", "namespace": "", "description": "查看所有 Pod", "requires_execution": true}

用户: "显示当前运行的容器"
输出: {"intent": "query", "task_type": "get", "target": "pod", "resource_name": "", "namespace": "default", "description": "查看 default 命名空间下所有正在运行的 Pod", "requires_execution": true}

用户: "pod 什么情况"
输出: {"intent": "query", "task_type": "get", "target": "pod", "resource_name": "", "namespace": "default", "description": "查看 default 命名空间下所有 Pod 的状态", "requires_execution": true}

用户: "重启 nginx 服务"
输出: {"intent": "operate", "task_type": "restart", "target": "deployment", "resource_name": "nginx", "namespace": "", "description": "重启 nginx deployment", "requires_execution": true}

用户: "我要重启这个default/nginx-56fcf95486-8t6qw"
输出: {"intent": "operate", "task_type": "restart", "target": "pod", "resource_name": "nginx-56fcf95486-8t6qw", "namespace": "default", "description": "重启 default 命名空间的 nginx-56fcf95486-8t6qw Pod", "requires_execution": true}

用户: "什么是 Deployment"
输出: {"intent": "query", "task_type": "other", "target": "unknown", "resource_name": "", "namespace": "", "description": "询问 Kubernetes 理论知识", "requires_execution": false}

用户: "我上一个问题是什么"
输出: {"intent": "query", "task_type": "other", "target": "unknown", "resource_name": "", "namespace": "", "description": "回顾上一个问题是什么", "requires_execution": false}

用户: "之前那条命令是什么"
输出: {"intent": "query", "task_type": "other", "target": "unknown", "resource_name": "", "namespace": "", "description": "回顾之前执行过什么命令", "requires_execution": false}

用户: "我们刚才聊了什么"
输出: {"intent": "query", "task_type": "other", "target": "unknown", "resource_name": "", "namespace": "", "description": "回顾刚才的对话内容", "requires_execution": false}

用户: "帮我看看集群状态"
输出: {"intent": "query", "task_type": "get", "target": "node", "resource_name": "", "namespace": "", "description": "查看集群整体状态", "requires_execution": true}
"""


class Orchestrator(BaseAgent):
    """编排者：解析意图，拆解任务"""

    def __init__(self):
        super().__init__(name="orchestrator")

    async def analyze(self, user_message: str, conversation_history: list = None) -> dict:
        """
        分析用户意图，返回包含 task_plan 和 reasoning 的字典
        
        参数:
            user_message: 用户当前消息
            conversation_history: 当前对话的历史消息列表（用于理解上下文）
        
        返回:
            {
                "reasoning": str,    # 思考链
                "task_plan": dict,   # 任务计划
            }
        """
        # 构建包含对话历史的 prompt
        prompt = user_message
        if conversation_history:
            history_text = "\n".join([
                f"{'用户' if m['role'] == 'user' else '助手'}: {m['content'][:200]}"
                for m in conversation_history[-5:]  # 最近5条
            ])
            prompt = f"""当前对话历史（最近5条）：
{history_text}

用户当前问题：{user_message}

请基于以上对话历史分析用户意图。"""
        
        result = await self.think_json_with_reasoning(
            system_prompt=ORCHESTRATOR_PROMPT,
            user_message=prompt,
        )

        reasoning = result.get("reasoning", "")
        task_plan = result.get("data", {})
        parse_failed = result.get("parse_failed", False)

        # 默认值兜底（含解析失败时：降级为“知识问答”，不进入集群执行流程，
        # 由 Reporter 结合知识库/文档内容正常回答用户问题）
        if not task_plan or parse_failed:
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
