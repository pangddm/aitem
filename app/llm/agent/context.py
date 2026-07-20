from app.memory.short_term import SessionMemory
from app.knowledge.service import KnowledgeService


class AgentContext:

    def __init__(
        self,
        memory: SessionMemory,
        knowledge_service: KnowledgeService,
    ):
        self.memory = memory
        self.knowledge = knowledge_service

    async def load(
        self,
        user_id: str,
        user_message: str,
    ):

        history = self.memory.load(user_id)

        knowledge = await self.knowledge.retrieve_context(
            kb_id=user_id,
            query=user_message,
        )

        return {

            "history": history,

            "knowledge": knowledge,

        }