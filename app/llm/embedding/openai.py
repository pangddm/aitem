"""OpenAI 兼容文本嵌入：网络/超时/5xx 自动重试。"""
from openai import AsyncOpenAI

from app.core.retry import retry_async

from .base import EmbeddingModel


class OpenAIEmbedding(EmbeddingModel):

    def __init__(
        self,
        client: AsyncOpenAI,
        model: str,
    ):
        self.client = client
        self.model = model

    async def embed(
        self,
        text: str,
    ) -> list[float]:

        response = await retry_async(
            lambda: self.client.embeddings.create(
                model=self.model,
                input=text,
            )
        )
        return response.data[0].embedding
