"""
知识库自动学习模块
每次成功诊断后，自动将（症状→命令→结果→解决方案）沉淀到知识库
形成飞轮效应：越用越聪明
"""

import asyncio
from datetime import datetime
from uuid import uuid4

from app.llm.agents.base_agent import BaseAgent
from app.knowledge.factory import knowledge_factory
from app.knowledge.models import CommandTrace, Incident, IncidentSource, KnowledgeCategory


LEARN_PROMPT = """
你是 Kubernetes 运维知识沉淀专家。

根据以下完整诊断过程，提取可复用的知识案例。

## 沉淀规则
1. 只沉淀有价值的案例：成功诊断且有明确根因和解决方案的
2. 如果只是简单查询（如 kubectl get pods 且一切正常），不需要沉淀
3. 如果执行失败或没有明确结论，不需要沉淀
4. 如果是常见问题且有明确解决方案，值得沉淀

## 提取要求（避免断章取义）
1. **symptom（症状）**：完整描述用户遇到的问题现象，包含错误状态（如 CrashLoopBackOff、ImagePullBackOff）
2. **root_cause（根因）**：基于命令输出的完整分析，不要只截取部分信息。必须包含关键技术细节（如内存限制值、镜像地址、端口配置等）
3. **solution（解决方案）**：完整的解决步骤，包含具体命令或配置修改值
4. **summary（摘要）**：一句话概括问题和解决方案
5. **title（标题）**：简洁但信息完整，包含关键资源类型和问题类型

## 输出格式（严格 JSON）
{
  "should_learn": true/false,
  "title": "案例标题（简洁但信息完整）",
  "category": "deployment | pod | service | network | storage | config | other",
  "symptom": "完整的问题现象描述",
  "root_cause": "基于完整输出的根因分析（包含技术细节）",
  "solution": "完整的解决方案（包含具体步骤和命令）",
  "summary": "一句话摘要"
}

## 示例

### 不需要沉淀的案例：
诊断过程：用户意图查看 Pod 状态，命令 kubectl get pods，输出全部 Running
→ {"should_learn": false}

### 需要沉淀的案例：
诊断过程：用户意图诊断 Pod CrashLoopBackOff
命令: kubectl describe pod nginx-xxx
输出: Last State: Terminated, Reason: OOMKilled, Exit Code: 137, Memory: 128Mi
观察: Pod 因内存不足被 OOMKill
→ {
  "should_learn": true,
  "title": "Pod OOMKilled 内存不足导致 CrashLoopBackOff",
  "category": "pod",
  "symptom": "Pod nginx-xxx 反复重启，状态为 CrashLoopBackOff，Last State 显示 OOMKilled",
  "root_cause": "Pod 内存限制 128Mi 过低，容器内存使用超过限制触发 OOMKiller，进程被 SIGKILL（Exit Code 137）",
  "solution": "1. 编辑 Deployment 修改 resources.limits.memory 为 256Mi\n2. kubectl apply -f deployment.yaml\n3. 确认新 Pod 正常 Running",
  "summary": "Pod 因内存限制 128Mi 不足导致 OOMKilled，增加至 256Mi 后解决"
}
"""


class AutoLearner(BaseAgent):
    """自动学习器：从诊断过程中提取可复用知识"""

    def __init__(self):
        super().__init__(name="auto_learner")

    async def should_learn(self, task_plan: dict, execution_result: dict, observation: dict) -> dict:
        """
        判断是否应该从本次诊断中学习

        返回:
            {
                "should_learn": bool,
                "incident": dict | None,  # 如果 should_learn=True
            }
        """
        # 快速过滤：不需要执行的、失败的、简单查询的不学
        if not task_plan.get("requires_execution"):
            return {"should_learn": False, "incident": None}

        if not execution_result.get("success"):
            return {"should_learn": False, "incident": None}

        # 简单查询操作不学
        task_type = task_plan.get("task_type", "")
        if task_type in ("get", "describe", "logs"):
            # 但如果 Observer 发现了问题（如 CrashLoopBackOff），仍然值得学
            status = observation.get("status", "")
            if status not in ("error", "warning"):
                return {"should_learn": False, "incident": None}

        # 用 LLM 判断是否值得学习（提供完整上下文，避免断章取义）
        learn_input = f"""
用户意图: {task_plan.get('description', '')}
任务类型: {task_plan.get('task_type', '')}
目标资源: {task_plan.get('target', '')} {task_plan.get('resource_name', '')}
执行命令: {execution_result.get('command', '')}
命令完整输出: {execution_result.get('result', '')[:3000]}
观察状态: {observation.get('status', '')}
观察发现: {observation.get('findings', '')}
观察详情: {observation.get('details', '')}
"""

        result = await self.think_json_with_reasoning(
            system_prompt=LEARN_PROMPT,
            user_message=learn_input,
        )

        data = result.get("data", {})
        should_learn = data.get("should_learn", False)

        if not should_learn:
            return {"should_learn": False, "incident": None}

        # 构造 Incident 对象
        # 将资源类型映射到知识分类（KnowledgeCategory）
        category_map = {
            "deployment": KnowledgeCategory.CHANGE,   # 部署/变更
            "pod": KnowledgeCategory.FAULT,           # Pod 故障
            "service": KnowledgeCategory.FAULT,       # 服务故障
            "network": KnowledgeCategory.FAULT,       # 网络故障
            "storage": KnowledgeCategory.FAULT,       # 存储故障
            "config": KnowledgeCategory.CONFIG,       # 配置
            "fault": KnowledgeCategory.FAULT,
            "performance": KnowledgeCategory.PERFORMANCE,
            "change": KnowledgeCategory.CHANGE,
            "doc": KnowledgeCategory.DOC,
        }

        incident_data = {
            "title": data.get("title", "未命名案例"),
            "category": category_map.get(data.get("category", "doc"), KnowledgeCategory.DOC),
            "symptom": data.get("symptom", ""),
            "root_cause": data.get("root_cause", ""),
            "solution": data.get("solution", ""),
            "summary": data.get("summary", ""),
            "commands": [
                CommandTrace(
                    command=execution_result.get("command", ""),
                    stdout=execution_result.get("result", "")[:2000],
                    stderr=execution_result.get("error", ""),
                )
            ],
            "context_text": f"用户意图: {task_plan.get('description', '')}\n命令: {execution_result.get('command', '')}\n输出: {execution_result.get('result', '')[:1000]}",
        }

        return {"should_learn": True, "incident": incident_data}

    async def learn_and_store(self, owner: str, task_plan: dict, execution_result: dict, observation: dict):
        """
        自动学习并存储到知识库
        这是一个后台任务，不应阻塞主流程
        """
        try:
            result = await self.should_learn(task_plan, execution_result, observation)
            if not result["should_learn"]:
                print(f"[AutoLearn] 本次诊断不需要沉淀")
                return

            incident_data = result["incident"]
            print(f"[AutoLearn] 沉淀知识: {incident_data['title']}")

            # 获取或创建用户的"自动学习"知识库（与手动上传的知识库隔离）
            AUTO_LEARN_KB_NAME = "自动学习"
            kbs = await knowledge_factory.kb_repository.list_by_owner(owner)
            kb_id = None
            for kb in kbs:
                if kb.name == AUTO_LEARN_KB_NAME:
                    kb_id = kb.id
                    break

            if not kb_id:
                kb_id = str(uuid4())
                now = datetime.utcnow()
                from app.knowledge.models import KnowledgeBase
                kb = KnowledgeBase(
                    id=kb_id,
                    owner=owner,
                    name=AUTO_LEARN_KB_NAME,
                    description="从诊断过程中自动沉淀的知识",
                    created_at=now,
                    updated_at=now,
                )
                await knowledge_factory.kb_repository.create(kb)
                print(f"[AutoLearn] 创建'自动学习'知识库: kb={kb_id}")

            # 构造 Incident
            now = datetime.utcnow()
            incident = Incident(
                id=str(uuid4()),
                kb_id=kb_id,
                document_id=None,  # 自动学习的没有关联文档
                owner=owner,
                source=IncidentSource.LEARNING,
                title=incident_data["title"],
                category=incident_data["category"],
                symptom=incident_data["symptom"],
                root_cause=incident_data["root_cause"],
                solution=incident_data["solution"],
                summary=incident_data["summary"],
                commands=incident_data["commands"],
                context_text=incident_data["context_text"],
                created_at=now,
                updated_at=now,
            )

            # 生成 embedding（使用工厂获取已配置的 EmbeddingService）
            emb_service = knowledge_factory.embedding_service
            text_for_embed = emb_service.build_incident_text(
                title=incident.title,
                summary=incident.summary,
                symptom=incident.symptom,
                root_cause=incident.root_cause,
                solution=incident.solution,
            )
            embedding = await emb_service.embed(text_for_embed)
            incident.embedding = embedding

            # 存储
            await knowledge_factory.incident_repository.create(incident)
            print(f"[AutoLearn] 知识沉淀成功: {incident.title}")

        except Exception as e:
            print(f"[AutoLearn] 知识沉淀失败: {e}")
            import traceback
            traceback.print_exc()