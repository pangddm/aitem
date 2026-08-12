from __future__ import annotations

import hashlib
from typing import Protocol

from app.core.config import (
    EMBEDDING_CACHE_ENABLED,
    EMBED_TITLE_REPEAT,
    EMBED_BATCH_SIZE,
    EMBED_BATCH_CONCURRENCY,
)


class EmbeddingModel(Protocol):
    """Any embedding model that can embed text."""

    async def embed(
        self,
        text: str,
    ) -> list[float]:
        ...


class EmbeddingService:

    def __init__(
        self,
        model: EmbeddingModel,
    ):
        self.model = model
        self._cache: dict[str, list[float]] = {}

    def _hash(self, text: str) -> str:
        return hashlib.sha1(text.encode("utf-8")).hexdigest()

    def clear_cache(self) -> None:
        self._cache.clear()

    async def aclose(self) -> None:
        """关闭底层 embedding 客户端的连接（异步）。"""
        import asyncio

        close = getattr(self.model, "close", None)
        if close is not None:
            if asyncio.iscoroutinefunction(close):
                await close()
            else:
                close()
        self.clear_cache()

    async def embed(
        self,
        text: str,
    ) -> list[float]:

        text = self._normalize(text)

        if EMBEDDING_CACHE_ENABLED:
            key = self._hash(text)
            if key in self._cache:
                return self._cache[key]

            vector = await self.model.embed(text)
            self._cache[key] = vector
            return vector

        return await self.model.embed(text)

    async def batch_embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:

        texts = [
            self._normalize(t)
            for t in texts
        ]

        if not texts:
            return []

        if not EMBEDDING_CACHE_ENABLED:
            return await self._raw_batch(texts)

        # 命中缓存的直接复用，只对缺失项调用模型
        keys = [self._hash(t) for t in texts]
        results: list[list[float]] = []
        missing: list[tuple[int, str]] = []
        for i, key in enumerate(keys):
            if key in self._cache:
                results.append(self._cache[key])
            else:
                results.append(None)
                missing.append((i, texts[i]))

        if missing:
            missing_texts = [t for _, t in missing]
            embedded = await self._raw_batch(missing_texts)
            for (i, _), vec in zip(missing, embedded):
                results[i] = vec
                self._cache[keys[i]] = vec

        return results

    async def _raw_batch(
        self,
        texts: list[str],
    ) -> list[list[float]]:

        if not texts:
            return []

        # 优先用模型的批量接口（一次 API 调用处理所有）；
        # 超过单批上限时分片并行，避免单次请求过大被上游限流/截断
        if hasattr(self.model, "batch_embed"):
            size = max(1, EMBED_BATCH_SIZE)
            if len(texts) <= size:
                return await self.model.batch_embed(texts)

            import asyncio

            chunks = [
                texts[i:i + size]
                for i in range(0, len(texts), size)
            ]
            concurrency = max(1, EMBED_BATCH_CONCURRENCY)
            semaphore = asyncio.Semaphore(concurrency)

            async def _one(chunk):
                async with semaphore:
                    return await self.model.batch_embed(chunk)

            parts = await asyncio.gather(
                *[_one(c) for c in chunks]
            )
            flattened: list[list[float]] = []
            for part in parts:
                flattened.extend(part)
            return flattened

        # Fallback: 并发控制
        import asyncio

        semaphore = asyncio.Semaphore(3)

        async def _embed_one(t: str) -> list[float]:
            async with semaphore:
                return await self.model.embed(t)

        results = await asyncio.gather(
            *[_embed_one(t) for t in texts]
        )

        return list(results)

    def build_incident_text(
        self,
        title: str,
        summary: str,
        symptom: str,
        root_cause: str,
        solution: str,
    ) -> str:
        """构造用于嵌入的文本。

        字段加权：标题重复 EMBED_TITLE_REPEAT 次（默认 2），使标题在向量里
        权重最高；其余字段各 1 次。对中文 embedding 模型是低成本有效的加权方式，
        且保持单向量嵌入、与查询向量直接可比。
        """
        title_block = "\n".join(
            f"Title:\n{title}" for _ in range(max(1, EMBED_TITLE_REPEAT))
        )

        return f"""
{title_block}

Summary:
{summary}

Symptom:
{symptom}

Root Cause:
{root_cause}

Solution:
{solution}
"""

    def _normalize(
        self,
        text: str,
    ) -> str:

        return (
            text
            .replace("\r", "")
            .replace("\t", " ")
            .strip()
        )
