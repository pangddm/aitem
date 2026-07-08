from app.memory.classes import MemoryType
from .base import BaseMemoryStrategy

class PreferenceStrategy(BaseMemoryStrategy):

    memory_type = MemoryType.PREFERENCE

    async def execute(self, memory):

        similar = await self.store.similarity_search(
            owner=memory.owner,
            query=memory.content,
            top_k=1
        )

        if similar:

            memory.id = similar[0].id

            await self.store.update(memory)

            return

        await self.store.save(memory)