from __future__ import annotations

from app.knowledge.embedding import EmbeddingService
from app.knowledge.models import Incident
from app.knowledge.repository.incident_repository import (
    IncidentRepository,
)
from app.knowledge.reranker import Reranker


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
        top_k: int = 10,
        rerank_top_k: int = 3,
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

        return await self.reranker.rerank(
            query=query,
            incidents=candidates,
            top_k=rerank_top_k,
        )

    async def vector_search(
        self,
        kb_id: str,
        query: str,
        top_k: int = 10,
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
        top_k: int = 10,
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
        top_k: int = 10,
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