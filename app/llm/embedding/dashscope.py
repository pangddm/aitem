from httpx import AsyncClient, Timeout

from app.core.config import (
    DASHSCOPE_API_KEY,
    DASHSCOPE_EMBEDDING_BASE_URL,
    DASHSCOPE_EMBEDDING_MODEL,
    EMBEDDING_DIM,
)

from .base import EmbeddingModel


class DashScopeEmbedding(EmbeddingModel):

    def __init__(self):
        if not DASHSCOPE_API_KEY:
            raise RuntimeError("DASHSCOPE_API_KEY is missing.")
        self.client = AsyncClient(
            timeout=Timeout(connect=5.0, read=60.0, write=15.0, pool=15.0)
        )
        self.headers = {
            "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
            "Content-Type": "application/json",
        }

    async def embed(self, text: str) -> list[float]:
        payload = {
            "model": DASHSCOPE_EMBEDDING_MODEL,
            "input": text,
            "dimensions": EMBEDDING_DIM,
        }
        resp = await self.client.post(
            DASHSCOPE_EMBEDDING_BASE_URL,
            headers=self.headers,
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]

    async def batch_embed(self, texts: list[str]) -> list[list[float]]:
        payload = {
            "model": DASHSCOPE_EMBEDDING_MODEL,
            "input": texts,
            "dimensions": EMBEDDING_DIM,
        }
        resp = await self.client.post(
            DASHSCOPE_EMBEDDING_BASE_URL,
            headers=self.headers,
            json=payload,
        )
        resp.raise_for_status()
        return [item["embedding"] for item in resp.json()["data"]]

    async def close(self):
        await self.client.aclose()
