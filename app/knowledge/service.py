from __future__ import annotations

from app.knowledge.ingestion import KnowledgeIngestionService
from app.knowledge.models import Incident
from app.knowledge.retriever import Retriever


class KnowledgeService:

    def __init__(
        self,
        ingestion_service: KnowledgeIngestionService,
        retriever: Retriever,
    ):
        self.ingestion_service = ingestion_service
        self.retriever = retriever

    # ===========================================
    # 上传知识
    # ===========================================

    async def upload_document(
        self,
        kb_id: str,
        file_path: str,
        owner: str = "default",
        document_id: str | None = None,
    ):

        return await self.ingestion_service.ingest(
            kb_id=kb_id,
            file_path=file_path,
            owner=owner,
            document_id=document_id,
        )

    # ===========================================
    # 上传文本
    # ===========================================

    async def upload_text(
        self,
        kb_id: str,
        filename: str,
        text: str,
        owner: str = "default",
    ):

        return await self.ingestion_service.ingest_text(
            kb_id=kb_id,
            filename=filename,
            text=text,
            owner=owner,
        )

    # ===========================================
    # 检索知识
    # ===========================================

    async def retrieve(
        self,
        kb_id: str,
        query: str,
        top_k: int = 3,
    ) -> list[Incident]:

        return await self.retriever.retrieve(
            kb_id=kb_id,
            query=query,
            rerank_top_k=top_k,
        )

    # ===========================================
    # 生成 Prompt Context
    # ===========================================

    async def retrieve_context(
        self,
        kb_id: str,
        query: str,
        top_k: int = 3,
    ) -> str:

        incidents = await self.retrieve(
            kb_id=kb_id,
            query=query,
            top_k=top_k,
        )

        if not incidents:
            return ""

        context = []

        for index, incident in enumerate(
            incidents,
            start=1,
        ):

            commands = []

            for cmd in incident.commands:

                commands.append(
                    f"""
Command:
{cmd.command}

Stdout:
{cmd.stdout}

Stderr:
{cmd.stderr}
"""
                )

            context.append(
                f"""
==========================
历史案例 {index}
==========================

分类: {incident.category.value}

标题:
{incident.title}

摘要:
{incident.summary}

症状/目的:
{incident.symptom}

根因/结论:
{incident.root_cause}

解决方案:
{incident.solution}

执行命令:

{''.join(commands)}

原文上下文 (Parent Chunk):
---
{incident.context_text[:1500] if incident.context_text else '(无)'}
---

"""
            )

        return "\n".join(context)