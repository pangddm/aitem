from __future__ import annotations

from app.knowledge.embedding import EmbeddingService
from app.knowledge.models import Incident
from app.knowledge.repository.incident_repository import (
    IncidentRepository,
)
from app.knowledge.reranker import Reranker
from app.core.config import RAG_TOP_K, RAG_RERANK_TOP_K, ENABLE_RERANK


class Retriever:

    def __init__(
        self,
        repository: IncidentRepository,
        embedding_service: EmbeddingService,
        reranker: Reranker,
    ):
        self.repository = repository
        self.embedding_service = embedding_service
        self.reranker = reranker

    async def retrieve(
        self,
        kb_id: str,
        query: str,
        top_k: int = RAG_TOP_K,
        rerank_top_k: int = RAG_RERANK_TOP_K,
    ) -> list[Incident]:
        """
        Retrieval Pipeline

        Query
            ↓
        Embedding
            ↓
        Vector Search
            ↓
        Keyword Search
            ↓
        Hybrid Merge
            ↓
        Reranker
            ↓
        Top K
        """

        embedding = await self.embedding_service.embed(
            query
        )

        candidates = await self.repository.hybrid_search(
            kb_id=kb_id,
            query=query,
            embedding=embedding,
            top_k=top_k,
        )

        if not candidates:
            return []

        # 默认关闭 LLM 精排（避免慢/不稳定），直接返回向量+关键词候选
        if ENABLE_RERANK:
            try:
                return await self.reranker.rerank(
                    query=query,
                    incidents=candidates,
                    top_k=rerank_top_k,
                )
            except Exception as e:
                print(f"[RAG] 精排异常，回退到原始候选: {type(e).__name__}: {e}")
                return candidates[:rerank_top_k]
        return candidates[:rerank_top_k]

    async def vector_search(
        self,
        kb_id: str,
        query: str,
        top_k: int = RAG_TOP_K,
    ) -> list[Incident]:

        embedding = await self.embedding_service.embed(
            query
        )

        return await self.repository.similarity_search(
            kb_id=kb_id,
            embedding=embedding,
            top_k=top_k,
        )

    async def keyword_search(
        self,
        kb_id: str,
        query: str,
        top_k: int = RAG_TOP_K,
    ) -> list[Incident]:

        return await self.repository.keyword_search(
            kb_id=kb_id,
            query=query,
            top_k=top_k,
        )

    async def hybrid_search(
        self,
        kb_id: str,
        query: str,
        top_k: int = RAG_TOP_K,
    ) -> list[Incident]:

        embedding = await self.embedding_service.embed(
            query
        )

        return await self.repository.hybrid_search(
            kb_id=kb_id,
            query=query,
            embedding=embedding,
            top_k=top_k,
        )