"""Retriever：向量/关键词融合召回 + 可选精排 + 来源标注 + 检索 trace。"""
from __future__ import annotations

import logging

from app.knowledge.embedding import EmbeddingService
from app.knowledge.models import Incident
from app.knowledge.repository.incident_repository import (
    IncidentRepository,
)
from app.knowledge.reranker import Reranker
from app.knowledge.ranking import rrf_fuse, min_score_filter
from app.core.config import (
    RAG_TOP_K,
    RAG_RERANK_TOP_K,
    ENABLE_RERANK,
    RAG_HYBRID_MODE,
    RAG_MIN_SCORE,
)

logger = logging.getLogger(__name__)


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
        Vector Search / Keyword Search
            ↓
        Hybrid Merge (RRF 或 线性加权)
            ↓
        最低分阈值过滤
            ↓
        Reranker
            ↓
        Top K + 来源标注 + trace 日志
        """

        if not query or not query.strip():
            return []

        # 查询向量化失败时降级为纯关键词召回，保证 embedding 故障时 RAG 不全挂
        try:
            embedding = await self.embedding_service.embed(query)
        except Exception as e:
            logger.warning(
                "[RAG] 查询向量化失败，降级为纯关键词召回: %s: %s",
                type(e).__name__, e,
            )
            embedding = None

        if RAG_HYBRID_MODE == "rrf":
            keyword_results = await self.repository.keyword_search(
                kb_id=kb_id, query=query, top_k=top_k,
            )
            if embedding is None:
                candidates = keyword_results[:top_k]
            else:
                vector_results = await self.repository.similarity_search(
                    kb_id=kb_id, embedding=embedding, top_k=top_k,
                )
                candidates = rrf_fuse(vector_results, keyword_results, top_k=top_k)
                # RRF 分数量纲小且非线性，不做绝对阈值过滤，交给 top_k 截断
        else:
            if embedding is None:
                candidates = await self.repository.keyword_search(
                    kb_id=kb_id, query=query, top_k=top_k,
                )
            else:
                candidates = await self.repository.hybrid_search(
                    kb_id=kb_id, query=query, embedding=embedding, top_k=top_k,
                )
            candidates = min_score_filter(candidates, RAG_MIN_SCORE)

        if not candidates:
            logger.info("[RAG] query=%r -> 0 候选", query)
            return []

        if ENABLE_RERANK and len(candidates) > rerank_top_k:
            try:
                results = await self.reranker.rerank(
                    query=query,
                    incidents=candidates,
                    top_k=rerank_top_k,
                )
            except Exception as e:
                logger.warning("[RAG] 精排异常，回退原始候选: %s: %s", type(e).__name__, e)
                results = candidates[:rerank_top_k]
        else:
            results = candidates[:rerank_top_k]

        self._log_trace(query, candidates, results)
        return results

    def _log_trace(
        self,
        query: str,
        candidates: list[Incident],
        results: list[Incident],
    ) -> None:
        """记录 检索 trace，便于排查召回与精排。"""
        top = [
            {
                "id": inc.id[:8],
                "title": (inc.title or "")[:40],
                "score": round(inc.score, 4) if inc.score else None,
                "src": inc.metadata.get("source_file", ""),
            }
            for inc in results[:5]
        ]
        logger.info(
            "[RAG] query=%r cand=%d top=%d detail=%r",
            query,
            len(candidates),
            len(results),
            top,
        )

    async def vector_search(
        self,
        kb_id: str,
        query: str,
        top_k: int = RAG_TOP_K,
    ) -> list[Incident]:

        embedding = await self.embedding_service.embed(query)
        return await self.repository.similarity_search(
            kb_id=kb_id, embedding=embedding, top_k=top_k,
        )

    async def keyword_search(
        self,
        kb_id: str,
        query: str,
        top_k: int = RAG_TOP_K,
    ) -> list[Incident]:

        return await self.repository.keyword_search(
            kb_id=kb_id, query=query, top_k=top_k,
        )

    async def hybrid_search(
        self,
        kb_id: str,
        query: str,
        top_k: int = RAG_TOP_K,
    ) -> list[Incident]:

        embedding = await self.embedding_service.embed(query)
        return await self.repository.hybrid_search(
            kb_id=kb_id, query=query, embedding=embedding, top_k=top_k,
        )
