from app.memory.strategies.base import BaseMemoryStrategy
from app.memory.classes import MemoryType

class ExperienceStrategy(BaseMemoryStrategy):
    memory_type = MemoryType.EXPERIENCE
    async def execute(self, memory):

        await self.store.save(memory)