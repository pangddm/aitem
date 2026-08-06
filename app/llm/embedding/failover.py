import asyncio

from app.core.config import EMBEDDING_FAILOVER_TIMEOUT

from .base import EmbeddingModel


class FailoverEmbedding(EmbeddingModel):
    """主用 provider 在超时间内未返回则切到备用 provider（切换后持续使用备用）。"""

    def __init__(self, primary, fallback, timeout=None):
        self.primary = primary
        self.fallback = fallback
        self.timeout = timeout if timeout is not None else EMBEDDING_FAILOVER_TIMEOUT
        self._switched = False

    def _switch(self, exc: Exception):
        if not self._switched:
            self._switched = True
            print(
                f"[Embedding] {type(self.primary).__name__} 超时/失败 ({exc}),"
                f" 切到 {type(self.fallback).__name__}"
            )

    async def embed(self, text: str) -> list[float]:
        if self._switched:
            return await self.fallback.embed(text)
        try:
            return await asyncio.wait_for(
                self.primary.embed(text), timeout=self.timeout
            )
        except Exception as e:
            self._switch(e)
            return await self.fallback.embed(text)

    async def batch_embed(self, texts: list[str]) -> list[list[float]]:
        if self._switched:
            return await self.fallback.batch_embed(texts)
        try:
            return await asyncio.wait_for(
                self.primary.batch_embed(texts), timeout=self.timeout
            )
        except Exception as e:
            self._switch(e)
            return await self.fallback.batch_embed(texts)

    async def close(self):
        await self.primary.close()
        await self.fallback.close()
