from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime
from enum import Enum
from uuid import uuid4

from app.knowledge.embedding import EmbeddingService
from app.knowledge.extractor import IncidentExtractor
from app.knowledge.models import (
    Document,
    DocumentStatus,
)
from app.knowledge.pipeline.cleaner import TextCleaner
from app.knowledge.pipeline.loader import DocumentLoader
from app.knowledge.pipeline.splitter import TextSplitter
from app.knowledge.repository.document_repository import (
    DocumentRepository,
)
from app.knowledge.repository.incident_repository import (
    IncidentRepository,
)


# ══════════════════════════════════════════════════════════
#  进度追踪（内存快照，供前端轮询）
# ══════════════════════════════════════════════════════════

class IngestStage(str, Enum):
    LOADING = "loading"
    CLEANING = "cleaning"
    EXTRACTING = "extracting"
    EMBEDDING = "embedding"
    STORING = "storing"
    DONE = "done"
    FAILED = "failed"
    DUPLICATE = "duplicate"


class IngestProgress:
    """单个文档的摄入进度快照"""

    def __init__(self, document_id: str, filename: str):
        self.document_id = document_id
        self.filename = filename
        self.stage = IngestStage.LOADING
        self.message = "开始解析..."
        self.pct = 0
        self.error: str | None = None
        self.incident_count = 0


class ProgressTracker:
    """全局进度追踪器（内存）"""

    def __init__(self):
        self._tasks: dict[str, IngestProgress] = {}

    def start(self, document_id: str, filename: str) -> IngestProgress:
        p = IngestProgress(document_id, filename)
        self._tasks[document_id] = p
        return p

    def update(self, document_id: str, **kwargs):
        if doc := self._tasks.get(document_id):
            for k, v in kwargs.items():
                setattr(doc, k, v)

    def get(self, document_id: str) -> IngestProgress | None:
        return self._tasks.get(document_id)

    def remove(self, document_id: str):
        self._tasks.pop(document_id, None)


# 全局单例
progress_tracker = ProgressTracker()


class KnowledgeIngestionService:

    def __init__(
        self,
        loader: DocumentLoader,
        cleaner: TextCleaner,
        splitter: TextSplitter,
        extractor: IncidentExtractor,
        embedding_service: EmbeddingService,
        document_repository: DocumentRepository,
        incident_repository: IncidentRepository,
    ):
        self.loader = loader
        self.cleaner = cleaner
        self.splitter = splitter
        self.extractor = extractor
        self.embedding_service = embedding_service
        self.document_repository = document_repository
        self.incident_repository = incident_repository
        self._extract_sem = asyncio.Semaphore(3)  # LLM 并发上限

    async def ingest(
        self,
        kb_id: str,
        file_path: str,
        owner: str,
        source: str = "upload",
        document_id: str | None = None,
    ):
        """
        上传一个文件进入知识库

        Pipeline

        file
            ↓
        loader
            ↓
        cleaner
            ↓
        splitter
            ↓
        extractor
            ↓
        embedding
            ↓
        postgres
        """
        if document_id is None:
            document_id = str(uuid4())

        progress_tracker.start(document_id, file_path)
        progress_tracker.update(
            document_id, stage=IngestStage.LOADING,
            message="解析文件中...", pct=5,
        )

        loaded = await self.loader.load(file_path)

        progress_tracker.update(
            document_id, stage=IngestStage.CLEANING,
            message="文本清洗中...", pct=15,
        )

        cleaned_text = self.cleaner.clean(
            loaded.text
        )

        # ── 去重：计算文件内容 MD5，同一用户下跨知识库不重复入库 ──
        content_hash = hashlib.md5(
            loaded.text.encode("utf-8")
        ).hexdigest()

        existing = await self.document_repository.get_by_hash(
            owner=owner,
            content_hash=content_hash,
        )
        if existing is not None:
            # 仅当该文档已成功入库（completed）时才视为“重复”，直接复用其知识
            if existing.parse_status == DocumentStatus.COMPLETED:
                progress_tracker.update(
                    document_id, stage=IngestStage.DUPLICATE,
                    message="已存在，跳过", pct=100,
                )
                # 已存在且成功入库，直接返回已有文档的 incidents
                return await self.incident_repository.list_by_document(
                    existing.id
                )
            # 已存在但是失败/中断的残留记录 → 不是真重复。
            # 清理该残留（否则每次上传都会“假重复”，RAG 里却永远没有该文件的知识），
            # 然后重新入库。
            if existing.parse_status in (
                DocumentStatus.FAILED,
                DocumentStatus.PENDING,
            ):
                await self.incident_repository.delete_by_document(existing.id)
                await self.document_repository.delete(existing.id)
        # ── 去重结束 ──

        now = datetime.utcnow()

        document = Document(

            id=document_id,

            owner=owner,

            kb_id=kb_id,

            filename=loaded.filename,

            mime_type=loaded.mime_type,

            file_size=loaded.file_size,

            source=source,

            origin_text="",

            ocr_text="",

            content_hash=content_hash,

            parse_status=DocumentStatus.PROCESSING,

            metadata=loaded.metadata,

            created_at=now,

            updated_at=now,
        )

        await self.document_repository.create(
            document
        )

        progress_tracker.update(
            document_id, stage=IngestStage.EXTRACTING,
            message="LLM 提取知识中...", pct=30,
        )
        await self._persist_progress(document_id, IngestStage.EXTRACTING, 30, "LLM 提取知识中...")

        # 整文交给 LLM 提取
        # 只有超大文档（>40000 字符）才分片，避免超出 LLM 上下文
        MAX_TEXT_FOR_SINGLE_EXTRACT = 40000
        parent_context = ""
        if len(cleaned_text) <= MAX_TEXT_FOR_SINGLE_EXTRACT:
            parent_context = cleaned_text
            incidents = await self.extractor.extract(
                kb_id=kb_id,
                document_id=document.id,
                text=cleaned_text,
                owner=owner,
            )
            all_incidents = incidents if incidents else []
        else:
            chunks = self.splitter.split(
                cleaned_text,
                chunk_size=30000,
            )
            # 并行提取每个 chunk（信号量控制 LLM 并发）
            async def _extract_one(text: str):
                async with self._extract_sem:
                    return await self.extractor.extract(
                        kb_id=kb_id,
                        document_id=document.id,
                        text=text,
                        owner=owner,
                    )

            tasks = [_extract_one(chunk.text) for chunk in chunks]
            chunk_results = await asyncio.gather(*tasks)
            all_incidents = []
            for chunk, incidents in zip(chunks, chunk_results):
                if incidents:
                    for inc in incidents:
                        inc.context_text = chunk.text
                    all_incidents.extend(incidents)

        if all_incidents:

            progress_tracker.update(
                document_id, stage=IngestStage.EMBEDDING,
                message=f"向量化 {len(all_incidents)} 条知识...", pct=60,
            )
            await self._persist_progress(document_id, IngestStage.EMBEDDING, 60, f"向量化 {len(all_incidents)} 条知识...")

            # 批量 embedding（一次 API 调用）
            embedding_texts = [
                self.embedding_service.build_incident_text(
                    title=inc.title,
                    summary=inc.summary,
                    symptom=inc.symptom,
                    root_cause=inc.root_cause,
                    solution=inc.solution,
                )
                for inc in all_incidents
            ]

            try:
                embeddings = await self.embedding_service.batch_embed(
                    embedding_texts
                )
            except Exception as emb_err:
                # 捕获 embedding 具体错误，向上抛出有意义的提示
                raise RuntimeError(
                    f"向量化失败（{len(all_incidents)} 条知识）：{emb_err}"
                ) from emb_err

            progress_tracker.update(
                document_id, stage=IngestStage.STORING,
                message="写入数据库...", pct=85,
            )
            await self._persist_progress(document_id, IngestStage.STORING, 85, "写入数据库...")

            for incident, embedding in zip(
                all_incidents,
                embeddings,
            ):
                incident.owner = owner
                if not incident.context_text and parent_context:
                    incident.context_text = parent_context
                incident.embedding = embedding
                incident.created_at = now
                incident.updated_at = now

            # 批量入库（一次事务）
            await self.incident_repository.batch_create(all_incidents)

        await self.document_repository.update_status(

            document.id,

            DocumentStatus.COMPLETED,
        )

        progress_tracker.update(
            document_id, stage=IngestStage.DONE,
            message=f"完成，提取 {len(all_incidents)} 条知识",
            pct=100, incident_count=len(all_incidents),
        )
        await self._persist_progress(document_id, IngestStage.DONE, 100, f"完成，提取 {len(all_incidents)} 条知识", len(all_incidents))

        return all_incidents

    async def _persist_progress(
        self,
        document_id: str,
        stage,
        pct: int,
        message: str,
        incident_count: int = 0,
    ) -> None:
        """把进度持久化到 DB，前端重新打开界面后仍能恢复进度显示"""
        if stage == IngestStage.FAILED:
            status = DocumentStatus.FAILED
        elif stage == IngestStage.DONE:
            status = DocumentStatus.COMPLETED
        else:
            status = DocumentStatus.PROCESSING
        try:
            await self.document_repository.update_progress(
                document_id,
                status,
                {
                    "stage": stage.value,
                    "pct": pct,
                    "message": message,
                    "error": None,
                    "incident_count": incident_count,
                },
            )
        except Exception:
            pass

    async def ingest_text(
        self,
        kb_id: str,
        filename: str,
        text: str,
        owner: str,
        source: str = "manual",
    ):
        """
        直接导入文本

        比如：

        markdown

        粘贴日志

        聊天记录

        Agent Learning
        """

        cleaned = self.cleaner.clean(
            text
        )

        # ── 去重（跨知识库）──
        content_hash = hashlib.md5(
            text.encode("utf-8")
        ).hexdigest()

        existing = await self.document_repository.get_by_hash(
            owner=owner,
            content_hash=content_hash,
        )
        if existing is not None:
            return await self.incident_repository.list_by_document(
                existing.id
            )
        # ── 去重结束 ──

        now = datetime.utcnow()

        document = Document(

            id=str(uuid4()),

            owner=owner,

            kb_id=kb_id,

            filename=filename,

            mime_type="text/plain",

            file_size=len(text.encode("utf-8")),

            source=source,

            origin_text="",

            ocr_text="",

            content_hash=content_hash,

            parse_status=DocumentStatus.PROCESSING,

            metadata={},

            created_at=now,

            updated_at=now,
        )

        await self.document_repository.create(
            document
        )

        MAX_TEXT_FOR_SINGLE_EXTRACT = 40000
        parent_context = ""
        if len(cleaned) <= MAX_TEXT_FOR_SINGLE_EXTRACT:
            parent_context = cleaned
            incidents = await self.extractor.extract(
                kb_id=kb_id,
                document_id=document.id,
                text=cleaned,
                owner=owner,
            )
            incidents = incidents if incidents else []
        else:
            chunks = self.splitter.split(
                cleaned,
                chunk_size=30000,
            )
            # 并行提取（信号量控制 LLM 并发）
            async def _extract_one(text: str):
                async with self._extract_sem:
                    return await self.extractor.extract(
                        kb_id=kb_id,
                        document_id=document.id,
                        text=text,
                        owner=owner,
                    )

            tasks = [_extract_one(chunk.text) for chunk in chunks]
            chunk_results = await asyncio.gather(*tasks)
            incidents = []
            for chunk, result in zip(chunks, chunk_results):
                if result:
                    for inc in result:
                        inc.context_text = chunk.text
                    incidents.extend(result)

        if incidents:

            texts = [
                self.embedding_service.build_incident_text(
                    title=i.title,
                    summary=i.summary,
                    symptom=i.symptom,
                    root_cause=i.root_cause,
                    solution=i.solution,
                )
                for i in incidents
            ]

            embeddings = await self.embedding_service.batch_embed(
                texts
            )

            for incident, embedding in zip(
                incidents,
                embeddings,
            ):
                incident.owner = owner
                if not incident.context_text and parent_context:
                    incident.context_text = parent_context
                incident.embedding = embedding
                incident.created_at = now
                incident.updated_at = now

            # 批量入库
            await self.incident_repository.batch_create(incidents)

        await self.document_repository.update_status(

            document.id,

            DocumentStatus.COMPLETED,
        )

        return incidents