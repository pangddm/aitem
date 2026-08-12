"""Jina 文本嵌入：429 按 Retry-After 退避重试；已去重重复的 batch_embed。"""
import asyncio

import httpx

from app.core.config import JINA_API_KEY, JINA_BASE_URL, JINA_MODEL

from .base import EmbeddingModel


class JinaEmbedding(EmbeddingModel):

    BASE_URL = JINA_BASE_URL
    MODEL = JINA_MODEL

    def __init__(self):
        if not JINA_API_KEY:
            raise RuntimeError("JINA_API_KEY is missing.")
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

    async def _post_with_retry(self, payload, label):
        last_exc = None
        for attempt in range(4):  # 1 + 3 重试
            response = await self.client.post(
                self.BASE_URL, headers=self.headers, json=payload
            )
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else 2 ** attempt
                print(
                    f"[Jina] 429 rate limited {label}, "
                    f"retrying in {wait:.1f}s (attempt {attempt + 1}/4)"
                )
                await asyncio.sleep(wait)
                last_exc = httpx.HTTPStatusError(
                    "429 Too Many Requests",
                    request=response.request,
                    response=response,
                )
                continue
            response.raise_for_status()
            return response
        raise last_exc

    async def embed(self, text: str) -> list[float]:
        payload = {"model": self.MODEL, "input": [{"text": text}]}
        resp = await self._post_with_retry(payload, "embed")
        return resp.json()["data"][0]["embedding"]

    async def batch_embed(self, texts: list[str]) -> list[list[float]]:
        payload = {"model": self.MODEL, "input": [{"text": t} for t in texts]}
        resp = await self._post_with_retry(payload, f"batch({len(texts)})")
        return [item["embedding"] for item in resp.json()["data"]]

    async def close(self):
        await self.client.aclose()
