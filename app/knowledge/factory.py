"""
Knowledge 模块的依赖装配工厂

用法:
    from app.knowledge.factory import KnowledgeFactory

    factory = KnowledgeFactory()
    service = factory.create_service()
"""

from __future__ import annotations

from app.db.postgres import postgres
from app.knowledge.embedding import EmbeddingService
from app.knowledge.extractor import IncidentExtractor
from app.knowledge.ingestion import KnowledgeIngestionService
from app.knowledge.pipeline.cleaner import TextCleaner
from app.knowledge.pipeline.loader import DocumentLoader
from app.knowledge.pipeline.splitter import TextSplitter
from app.knowledge.reranker import Reranker
from app.knowledge.repository.document_repository import (
    DocumentRepository,
)
from app.knowledge.repository.incident_repository import (
    IncidentRepository,
)
from app.knowledge.repository.knowledge_base_repository import (
    KnowledgeBaseRepository,
)
from app.knowledge.retriever import Retriever
from app.knowledge.service import KnowledgeService
from app.llm.client import client as llm_client
from app.llm.embedding.factory import get_embedding


class KnowledgeFactory:
    """一站式工厂，组装 Knowledge 模块的所有依赖"""

    def __init__(self):
        self._embedding_model = None
        self._embedding_service = None
        self._incident_repo = None
        self._document_repo = None
        self._kb_repo = None
        self._loader = None
        self._cleaner = None
        self._splitter = None
        self._extractor = None
        self._reranker = None
        self._retriever = None
        self._ingestion = None
        self._service = None

    # ── Repositories ──────────────────────────────────────

    @property
    def kb_repository(self) -> KnowledgeBaseRepository:
        if self._kb_repo is None:
            self._kb_repo = KnowledgeBaseRepository(
                pool=postgres.pool,
            )
        return self._kb_repo

    @property
    def document_repository(self) -> DocumentRepository:
        if self._document_repo is None:
            self._document_repo = DocumentRepository(
                pool=postgres.pool,
            )
        return self._document_repo

    @property
    def incident_repository(self) -> IncidentRepository:
        if self._incident_repo is None:
            self._incident_repo = IncidentRepository(
                pool=postgres.pool,
            )
        return self._incident_repo

    # ── Embedding ─────────────────────────────────────────

    @property
    def embedding_service(self) -> EmbeddingService:
        if self._embedding_service is None:
            if self._embedding_model is None:
                self._embedding_model = get_embedding()
            self._embedding_service = EmbeddingService(
                model=self._embedding_model,
            )
        return self._embedding_service

    # ── Pipeline ──────────────────────────────────────────

    @property
    def loader(self) -> DocumentLoader:
        if self._loader is None:
            self._loader = DocumentLoader()
        return self._loader

    @property
    def cleaner(self) -> TextCleaner:
        if self._cleaner is None:
            self._cleaner = TextCleaner()
        return self._cleaner

    @property
    def splitter(self) -> TextSplitter:
        if self._splitter is None:
            self._splitter = TextSplitter()
        return self._splitter

    @property
    def extractor(self) -> IncidentExtractor:
        if self._extractor is None:
            self._extractor = IncidentExtractor(
                llm_client=llm_client,
            )
        return self._extractor

    # ── Retriever / Reranker ──────────────────────────────

    @property
    def reranker(self) -> Reranker:
        if self._reranker is None:
            self._reranker = Reranker(
                llm_client=llm_client,
            )
        return self._reranker

    @property
    def retriever(self) -> Retriever:
        if self._retriever is None:
            self._retriever = Retriever(
                repository=self.incident_repository,
                embedding_service=self.embedding_service,
                reranker=self.reranker,
            )
        return self._retriever

    # ── Ingestion ─────────────────────────────────────────

    @property
    def ingestion_service(self) -> KnowledgeIngestionService:
        if self._ingestion is None:
            self._ingestion = KnowledgeIngestionService(
                loader=self.loader,
                cleaner=self.cleaner,
                splitter=self.splitter,
                extractor=self.extractor,
                embedding_service=self.embedding_service,
                document_repository=self.document_repository,
                incident_repository=self.incident_repository,
            )
        return self._ingestion

    # ── Knowledge Service ─────────────────────────────────

    @property
    def service(self) -> KnowledgeService:
        if self._service is None:
            self._service = KnowledgeService(
                ingestion_service=self.ingestion_service,
                retriever=self.retriever,
            )
        return self._service

    # ── Convenience ───────────────────────────────────────

    def create_service(self) -> KnowledgeService:
        return self.service


# 全局单例
knowledge_factory = KnowledgeFactory()
