from __future__ import annotations

from typing import Protocol


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

    async def embed(
        self,
        text: str,
    ) -> list[float]:

        text = self._normalize(text)

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

        # 优先用模型的批量接口（一次 API 调用处理所有）
        if hasattr(self.model, "batch_embed"):
            return await self.model.batch_embed(texts)

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

        return f"""
Title:
{title}

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