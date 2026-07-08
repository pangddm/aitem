from app.memory.strategies.base import BaseMemoryStrategy
from app.memory.classes import MemoryType

class FaultStrategy(BaseMemoryStrategy):
    memory_type = MemoryType.FAULT
    async def execute(self, memory):

        await self.store.save(memory)