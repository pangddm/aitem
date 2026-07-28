"""
Command Rewriter Agent — 用户命令重写
职责：将用户模糊、混乱的自然语言问题重写为清晰、结构化的诊断描述
帮助 Orchestrator 更准确地分析意图
"""
from app.llm.agents.base_agent import BaseAgent


REWRITER_PROMPT = """你是 Kubernetes 问题诊断助手。你的任务是将用户模糊、混乱、不完整的问题描述重写为清晰、结构化的诊断请求。

重写规则：
1. 识别用户真正想解决的问题（诊断、修复、查询、操作等）
2. 补充缺失的关键信息（如果用户提到了 Pod 名、namespace、错误类型等，保留并突出）
3. 如果用户描述很模糊（如"pod 有问题"），扩展为具体的诊断方向
4. 保持简洁，不要添加用户没提到的假设性内容
5. 使用专业但易懂的中文表达
6. 【重要】clarification_needed 只在以下情况设为 true：
   - 用户提到了具体的资源（如 Pod 名）但缺少关键信息（如 namespace）
   - 用户描述了一个需要操作的具体问题但信息严重不足
   - 对于闲聊、询问原因、理论知识、创建/模拟问题等请求，clarification_needed 必须为 false
   - 当用户请求"创建问题"、"模拟故障"等时，应该理解为用户想要你帮忙操作，clarification_needed 为 false
7. 【重要】clarification_question 必须简洁，不要使用"请问"等冗余词汇，直接提问即可
8. 【重要】对于模糊但常见的运维问题（如"pod 起不来"、"检查集群状态"、"看看 pod"等），如果用户没有提供 namespace，默认使用 "default" 命名空间，不要向用户提问。clarification_needed 设为 false，clarification_question 设为空字符串。
9. 【重要】对于询问"上一个问题"、"之前的问题"、"历史问题"等上下文回顾类问题，不要添加任何假设性内容。重写为"用户询问上一轮对话中提出的问题"即可，不要猜测具体内容。original_intent 设为 "chat"，key_entities 全部设为空。

输出格式（严格 JSON）：
{
  "rewritten": "重写后的清晰问题描述",
  "original_intent": "diagnose|fix|query|operate|chat",
  "key_entities": {
    "resource_type": "pod|deployment|service|node|namespace|unknown",
    "resource_name": "提取到的资源名称，没有则为空",
    "namespace": "提取到的命名空间，没有则默认为 default",
    "error_type": "提取到的错误类型，如 ImagePullBackOff、CrashLoopBackOff、Pending 等，没有则为空"
  },
  "clarification_needed": false,
  "clarification_question": ""
}

示例：
用户: "pod 起不来"
输出: {"rewritten": "请帮我诊断 default 命名空间下 Pod 启动失败的问题，检查 Pod 状态和事件日志", "original_intent": "diagnose", "key_entities": {"resource_type": "pod", "resource_name": "", "namespace": "default", "error_type": ""}, "clarification_needed": false, "clarification_question": ""}

用户: "test 命名空间下有个 bad-image-pod 一直 ImagePullBackOff"
输出: {"rewritten": "请帮我修复 test 命名空间下 bad-image-pod 的 ImagePullBackOff 问题，检查镜像地址和拉取配置", "original_intent": "fix", "key_entities": {"resource_type": "pod", "resource_name": "bad-image-pod", "namespace": "test", "error_type": "ImagePullBackOff"}, "clarification_needed": false, "clarification_question": ""}

用户: "帮我看看集群状态"
输出: {"rewritten": "请帮我检查 Kubernetes 集群整体状态，包括节点健康、Pod 运行情况和资源使用", "original_intent": "query", "key_entities": {"resource_type": "unknown", "resource_name": "", "namespace": "default", "error_type": ""}, "clarification_needed": false, "clarification_question": ""}

用户: "test 命名空间下有个 pod 叫 nginx-xxx 状态不对"
输出: {"rewritten": "请帮我诊断 test 命名空间下 nginx-xxx Pod 的状态异常问题，检查 Pod 详情和事件", "original_intent": "diagnose", "key_entities": {"resource_type": "pod", "resource_name": "nginx-xxx", "namespace": "test", "error_type": ""}, "clarification_needed": false, "clarification_question": ""}

用户: "我上一个问题是啥"
输出: {"rewritten": "用户询问上一轮对话中提出的问题", "original_intent": "chat", "key_entities": {"resource_type": "unknown", "resource_name": "", "namespace": "", "error_type": ""}, "clarification_needed": false, "clarification_question": ""}

用户: "之前我问了什么"
输出: {"rewritten": "用户询问之前对话中提出的问题", "original_intent": "chat", "key_entities": {"resource_type": "unknown", "resource_name": "", "namespace": "", "error_type": ""}, "clarification_needed": false, "clarification_question": ""}
"""


class CommandRewriter(BaseAgent):
    """用户命令重写 Agent"""

    def __init__(self):
        super().__init__(name="command_rewriter")

    async def rewrite(self, user_message: str, conversation_history: list = None) -> dict:
        """
        重写用户模糊/混乱的问题描述

        参数:
            user_message: 用户当前消息
            conversation_history: 对话历史 [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]

        返回:
            {
                "reasoning": str,
                "rewritten": str,           # 重写后的清晰描述
                "original_intent": str,     # 原始意图
                "key_entities": dict,       # 提取的关键实体
                "clarification_needed": bool,
                "clarification_question": str,
            }
        """
        # 检测是否为上下文回顾类问题（如"上一个问题是啥"、"之前问了什么"等）
        # 这类问题不应该传入对话历史，避免 LLM 把历史内容混入重写结果
        context_review_keywords = [
            "上一个问题", "上一个", "之前的问题", "之前问", "刚才问",
            "历史问题", "历史记录", "上一轮", "上一次", "刚才说的",
            "我之前", "我刚才", "我上次",
        ]
        is_context_review = any(kw in user_message for kw in context_review_keywords)
        
        # 构建包含对话上下文的 prompt
        user_prompt = f"用户当前问题: {user_message}"
        if conversation_history and len(conversation_history) > 0 and not is_context_review:
            # 取最近 6 轮对话（12 条消息）
            recent = conversation_history[-12:]
            history_text = "\n".join([
                f"{'用户' if m['role'] == 'user' else '助手'}: {m.get('content', '')[:300]}"
                for m in recent
            ])
            user_prompt = (
                f"## 对话历史（最近几轮）\n{history_text}\n\n"
                f"## 用户当前问题\n{user_message}\n\n"
                f"请结合对话历史理解用户意图，重写当前问题。"
            )
        elif is_context_review:
            # 上下文回顾类问题，不传入对话历史
            user_prompt = (
                f"## 用户当前问题\n{user_message}\n\n"
                f"注意：这是一个上下文回顾类问题，用户想了解之前对话的内容。"
                f"请直接重写为'用户询问之前对话中提出的问题'，不要添加任何假设性内容。"
            )
        
        result = await self.think_json_with_reasoning(
            system_prompt=REWRITER_PROMPT,
            user_message=user_prompt,
        )

        reasoning = result.get("reasoning", "")
        data = result.get("data", {})

        # 后处理：强制将 clarification_needed 设为 false，避免 LLM 误判
        # 系统会自动处理模糊问题，不需要向用户提问
        
        # 对上下文回顾类问题，直接覆盖重写结果，避免 LLM 添加假设性内容
        if is_context_review:
            rewritten = "用户询问之前对话中提出的问题"
            return {
                "reasoning": reasoning,
                "rewritten": rewritten,
                "original_intent": "chat",
                "key_entities": {
                    "resource_type": "unknown",
                    "resource_name": "",
                    "namespace": "",
                    "error_type": "",
                },
                "clarification_needed": False,
                "clarification_question": "",
            }
        
        return {
            "reasoning": reasoning,
            "rewritten": data.get("rewritten", user_message),
            "original_intent": data.get("original_intent", "chat"),
            "key_entities": data.get("key_entities", {}),
            "clarification_needed": False,
            "clarification_question": "",
        }
