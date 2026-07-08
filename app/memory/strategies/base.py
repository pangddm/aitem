from abc import ABC
from abc import abstractmethod

from app.memory.classes import Memory
from app.memory.long_term import LongTermStore


class BaseMemoryStrategy(ABC):

    registry = {}

    memory_type = None

    def __init_subclass__(cls):

        super().__init_subclass__()

        if cls.memory_type is not None:

            BaseMemoryStrategy.registry[
                cls.memory_type
            ] = cls

    def __init__(self, store: LongTermStore):

        self.store = store

    @abstractmethod
    async def execute(
        self,
        memory: Memory
    ):
        pass