from __future__ import annotations

import asyncio
from datetime import datetime
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
        owner: str = "default",
        source: str = "upload",
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

        loaded = await self.loader.load(file_path)

        cleaned_text = self.cleaner.clean(
            loaded.text
        )

        now = datetime.utcnow()

        document = Document(

            id=str(uuid4()),

            owner=owner,

            kb_id=kb_id,

            filename=loaded.filename,

            mime_type=loaded.mime_type,

            file_size=loaded.file_size,

            source=source,

            origin_text=loaded.text,

            ocr_text=cleaned_text,

            parse_status=DocumentStatus.PROCESSING,

            metadata=loaded.metadata,

            created_at=now,

            updated_at=now,
        )

        await self.document_repository.create(
            document
        )

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

            embeddings = await self.embedding_service.batch_embed(
                embedding_texts
            )

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

        return all_incidents

    async def ingest_text(
        self,
        kb_id: str,
        filename: str,
        text: str,
        owner: str = "default",
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

        now = datetime.utcnow()

        document = Document(

            id=str(uuid4()),

            owner=owner,

            kb_id=kb_id,

            filename=filename,

            mime_type="text/plain",

            file_size=len(text.encode("utf-8")),

            source=source,

            origin_text=text,

            ocr_text=cleaned,

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