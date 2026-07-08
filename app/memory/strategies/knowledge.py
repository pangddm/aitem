from app.memory.strategies.base import BaseMemoryStrategy
from app.memory.classes import MemoryType

class KnowledgeStrategy(BaseMemoryStrategy):
    memory_type = MemoryType.KNOWLEDGE

    async def execute(self, memory):

        similar = await self.store.similarity_search(
            owner=memory.owner,
            query=memory.content,
            top_k=1
        )

        if similar:

            return

        await self.store.save(memory)