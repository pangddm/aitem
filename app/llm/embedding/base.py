from abc import ABC
from abc import abstractmethod


class EmbeddingModel(ABC):

    @abstractmethod
    async def embed(
        self,
        text: str
    ) -> list[float]:
        """将文本转换为向量"""
        pass