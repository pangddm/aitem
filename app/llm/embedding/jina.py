import asyncio

import httpx

from app.core.config import JINA_API_KEY

from .base import EmbeddingModel


class JinaEmbedding(EmbeddingModel):

    BASE_URL = "https://api.jina.ai/v1/embeddings"

    MODEL = "jina-embeddings-v5-text-small"

    def __init__(self):

        if not JINA_API_KEY:

            raise RuntimeError(
                "JINA_API_KEY is missing."
            )

        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=5.0,
                read=30.0,
                write=15.0,
                pool=15.0,
            )
        )

        self.headers = {
            "Authorization": f"Bearer {JINA_API_KEY}",
            "Content-Type": "application/json",
        }

    async def embed(
        self,
        text: str,
        max_retries: int = 3,
    ) -> list[float]:

        payload = {
            "model": self.MODEL,
            "input": [
                {
                    "text": text
                }
            ]
        }

        last_exc = None
        for attempt in range(max_retries + 1):
            response = await self.client.post(
                self.BASE_URL,
                headers=self.headers,
                json=payload,
            )

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else 2 ** attempt
                print(
                    f"[Jina] 429 rate limited, "
                    f"retrying in {wait:.1f}s "
                    f"(attempt {attempt + 1}/{max_retries + 1})"
                )
                await asyncio.sleep(wait)
                last_exc = httpx.HTTPStatusError(
                    "429 Too Many Requests",
                    request=response.request,
                    response=response,
                )
                continue

            response.raise_for_status()
            return response.json()["data"][0]["embedding"]

        raise last_exc

    async def batch_embed(
        self,
        texts: list[str],
        max_retries: int = 3,
    ) -> list[list[float]]:
        """批量 embedding — 一次 API 调用处理所有文本，避免并发限流"""

        payload = {
            "model": self.MODEL,
            "input": [{"text": t} for t in texts],
        }

        last_exc = None
        for attempt in range(max_retries + 1):
            response = await self.client.post(
                self.BASE_URL,
                headers=self.headers,
                json=payload,
            )

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else 2 ** attempt
                print(
                    f"[Jina] 429 rate limited (batch {len(texts)}), "
                    f"retrying in {wait:.1f}s "
                    f"(attempt {attempt + 1}/{max_retries + 1})"
                )
                await asyncio.sleep(wait)
                last_exc = httpx.HTTPStatusError(
                    "429 Too Many Requests",
                    request=response.request,
                    response=response,
                )
                continue

            response.raise_for_status()
            data = response.json()["data"]
            return [item["embedding"] for item in data]

        raise last_exc

    async def batch_embed(
        self,
        texts: list[str],
        max_retries: int = 3,
    ) -> list[list[float]]:
        """批量 embedding，一次 API 调用处理多条文本（避免 429）"""

        payload = {
            "model": self.MODEL,
            "input": [
                {"text": t} for t in texts
            ],
        }

        last_exc = None
        for attempt in range(max_retries + 1):
            response = await self.client.post(
                self.BASE_URL,
                headers=self.headers,
                json=payload,
            )

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else 2 ** attempt
                print(
                    f"[Jina] 429 batch rate limited, "
                    f"retrying in {wait:.1f}s "
                    f"(attempt {attempt + 1}/{max_retries + 1})"
                )
                await asyncio.sleep(wait)
                last_exc = httpx.HTTPStatusError(
                    "429 Too Many Requests",
                    request=response.request,
                    response=response,
                )
                continue

            response.raise_for_status()
            data = response.json()["data"]
            return [item["embedding"] for item in data]

        raise last_exc
    
    async def close(self):

        await self.client.aclose()