from openai import AsyncOpenAI

from .base import EmbeddingModel


class OpenAIEmbedding(EmbeddingModel):

    def __init__(

        self,

        client: AsyncOpenAI,

        model: str

    ):

        self.client = client

        self.model = model

    async def embed(
        self,
        text: str
    ) -> list[float]:

        response = await self.client.embeddings.create(

            model=self.model,

            input=text

        )

        return response.data[0].embedding