import httpx

from app.core.config import JINA_API_KEY

from .base import EmbeddingModel


class JinaEmbedding(EmbeddingModel):

    BASE_URL = "https://api.jina.ai/v1/embeddings"

    MODEL = "jina-embeddings-v4"

    def __init__(self):

        if not JINA_API_KEY:

            raise RuntimeError(
                "JINA_API_KEY is missing."
            )

        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=60.0,
                write=30.0,
                pool=30.0,
            )
        )

        self.headers = {
            "Authorization": f"Bearer {JINA_API_KEY}",
            "Content-Type": "application/json",
        }

    async def embed(
        self,
        text: str
    ) -> list[float]:

        payload = {
            "model": self.MODEL,
            "input": [
                {
                    "text": text
                }
            ]
        }

        response = await self.client.post(
            self.BASE_URL,
            headers=self.headers,
            json=payload
        )

        response.raise_for_status()

        return response.json()["data"][0]["embedding"]
    
    async def close(self):

        await self.client.aclose()