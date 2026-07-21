"""
知识库 (RAG) API

提供知识库管理、文档上传（含批量）、检索等功能。
"""

from __future__ import annotations

import os
import traceback
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse

from app.knowledge.factory import knowledge_factory
from app.knowledge.models import (
    IncidentSource,
    KnowledgeBase,
)

router = APIRouter(
    prefix="/knowledge",
    tags=["knowledge"],
)

UPLOAD_DIR = "./data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ══════════════════════════════════════════════════════════
#  知识库 CRUD
# ══════════════════════════════════════════════════════════


@router.post("/kb")
async def create_knowledge_base(
    owner: str = Form(...),
    name: str = Form(...),
    description: str | None = Form(None),
):
    """创建知识库"""
    now = datetime.utcnow()
    kb = KnowledgeBase(
        id=str(uuid4()),
        owner=owner,
        name=name,
        description=description,
        created_at=now,
        updated_at=now,
    )
    await knowledge_factory.kb_repository.create(kb)
    return {"success": True, "kb_id": kb.id}


@router.get("/kb/list")
async def list_knowledge_bases(
    owner: str = Query(...),
):
    """列出用户的所有知识库"""
    kbs = await knowledge_factory.kb_repository.list_by_owner(owner)
    return {"success": True, "data": kbs}


@router.get("/kb/{kb_id}")
async def get_knowledge_base(kb_id: str):
    """获取知识库详情"""
    kb = await knowledge_factory.kb_repository.get(kb_id)
    if kb is None:
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": "知识库不存在"},
        )
    return {"success": True, "data": kb}


@router.put("/kb/{kb_id}")
async def update_knowledge_base(
    kb_id: str,
    name: str | None = Form(None),
    description: str | None = Form(None),
    is_public: bool | None = Form(None),
):
    """更新知识库"""
    kb = await knowledge_factory.kb_repository.get(kb_id)
    if kb is None:
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": "知识库不存在"},
        )
    if name is not None:
        kb.name = name
    if description is not None:
        kb.description = description
    if is_public is not None:
        kb.is_public = is_public
    kb.updated_at = datetime.utcnow()
    await knowledge_factory.kb_repository.update(kb)
    return {"success": True, "message": "更新成功"}


@router.delete("/kb/{kb_id}")
async def delete_knowledge_base(kb_id: str):
    """删除知识库（级联删除所有文档和案例）"""
    await knowledge_factory.kb_repository.delete(kb_id)
    return {"success": True, "message": "知识库已删除"}


# ══════════════════════════════════════════════════════════
#  文档上传
# ══════════════════════════════════════════════════════════


@router.post("/kb/{kb_id}/upload")
async def upload_document(
    kb_id: str,
    owner: str = Form(...),
    file: UploadFile = File(...),
):
    """
    上传单个文档到知识库（异步处理）

    保存文件后立即返回 document_id，后台处理。
    前端通过 GET /knowledge/document/{document_id}/status 轮询进度。
    """
    import asyncio as _asyncio

    document_id = str(uuid4())
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # 后台异步处理（不阻塞 HTTP 响应）
    _asyncio.create_task(
        _process_upload_bg(
            kb_id=kb_id,
            owner=owner,
            file_path=file_path,
            document_id=document_id,
        )
    )

    return {
        "success": True,
        "document_id": document_id,
        "filename": file.filename,
        "message": "已接收，后台处理中",
    }


async def _process_upload_bg(
    kb_id: str,
    owner: str,
    file_path: str,
    document_id: str,
):
    """后台处理上传的文件"""
    from app.knowledge.ingestion import progress_tracker, IngestStage
    from app.knowledge.models import DocumentStatus

    try:
        await knowledge_factory.service.upload_document(
            kb_id=kb_id,
            file_path=file_path,
            owner=owner,
            document_id=document_id,
        )
    except Exception as e:
        traceback.print_exc()
        progress_tracker.update(
            document_id,
            stage=IngestStage.FAILED,
            message=str(e)[:500],
        )
        # 同步更新 DB 状态，防止重启后残留 PROCESSING
        try:
            await knowledge_factory.document_repository.update_status(
                document_id,
                DocumentStatus.FAILED,
            )
        except Exception:
            pass


@router.get("/document/{document_id}/status")
async def get_document_status(document_id: str):
    """
    轮询文档处理进度

    返回:
        stage: loading|cleaning|extracting|embedding|storing|done|failed|duplicate
        message: 当前阶段描述
        pct: 进度百分比 0-100
    """
    from app.knowledge.ingestion import progress_tracker

    progress = progress_tracker.get(document_id)
    if progress is not None:
        return {
            "success": True,
            "document_id": progress.document_id,
            "filename": progress.filename,
            "stage": progress.stage.value,
            "message": progress.message,
            "pct": progress.pct,
            "incident_count": progress.incident_count,
            "error": progress.error,
        }

    # progress_tracker 无记录（后端重启过）→ 查 DB 真实状态
    doc = await knowledge_factory.document_repository.get(document_id)
    if doc is None:
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": "文档不存在"},
        )

    if doc.parse_status.value == "completed":
        return {
            "success": True,
            "document_id": document_id,
            "filename": doc.filename,
            "stage": "done",
            "message": "已完成（历史记录）",
            "pct": 100,
            "incident_count": 0,
            "error": None,
        }
    elif doc.parse_status.value == "failed":
        return {
            "success": True,
            "document_id": document_id,
            "filename": doc.filename,
            "stage": "failed",
            "message": "处理失败",
            "pct": 0,
            "incident_count": 0,
            "error": "后台处理异常",
        }
    else:
        # processing / pending → 可能后端崩了重启
        return {
            "success": True,
            "document_id": document_id,
            "filename": doc.filename,
            "stage": "processing",
            "message": "处理中断（后端可能已重启），请重新上传",
            "pct": 0,
            "incident_count": 0,
            "error": None,
        }


@router.post("/kb/{kb_id}/text")
async def upload_text(
    kb_id: str,
    owner: str = Form(...),
    filename: str = Form(...),
    text: str = Form(...),
):
    """
    直接粘贴文本到知识库

    适用于: 日志粘贴、聊天记录、Markdown 笔记等
    """
    try:
        incidents = await knowledge_factory.service.upload_text(
            kb_id=kb_id,
            filename=filename,
            text=text,
            owner=owner,
        )
        return {
            "success": True,
            "filename": filename,
            "incidents": len(incidents),
            "data": incidents,
        }
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": str(e),
            },
        )


# ══════════════════════════════════════════════════════════
#  批量上传
# ══════════════════════════════════════════════════════════


@router.post("/kb/{kb_id}/batch-upload")
async def batch_upload_documents(
    kb_id: str,
    owner: str = Form(...),
    files: list[UploadFile] = File(...),
):
    """
    批量上传多个文档到知识库

    可以一次性选择多个文件，逐个解析并入库。
    使用方式 (Python requests):

        import requests
        url = "http://localhost:8000/knowledge/kb/<kb_id>/batch-upload"
        files = [
            ("files", ("故障1.log", open("故障1.log", "rb"))),
            ("files", ("故障2.md", open("故障2.md", "rb"))),
        ]
        resp = requests.post(
            url,
            data={"owner": "your_name"},
            files=files,
        )

    curl 示例:

        curl -X POST "http://localhost:8000/knowledge/kb/{kb_id}/batch-upload" \\
            -F "owner=admin" \\
            -F "files=@故障1.log" \\
            -F "files=@故障2.md"
    """
    results = []
    total_incidents = 0
    has_error = False

    for file in files:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        try:
            incidents = await knowledge_factory.service.upload_document(
                kb_id=kb_id,
                file_path=file_path,
                owner=owner,
            )
            total_incidents += len(incidents)
            results.append(
                {
                    "file": file.filename,
                    "status": "success",
                    "incidents": len(incidents),
                }
            )
        except Exception as e:
            has_error = True
            results.append(
                {
                    "file": file.filename,
                    "status": "failed",
                    "error": str(e),
                }
            )

    return {
        "success": not has_error,
        "total_files": len(files),
        "total_incidents": total_incidents,
        "results": results,
    }


# ══════════════════════════════════════════════════════════
#  检索
# ══════════════════════════════════════════════════════════


@router.get("/kb/{kb_id}/search")
async def search_knowledge_base(
    kb_id: str,
    query: str = Query(...),
    top_k: int = Query(3, ge=1, le=20),
):
    """
    在知识库中检索相关案例

    流程: Query → Embedding → Hybrid Search → Reranker → Top K
    """
    try:
        incidents = await knowledge_factory.service.retrieve(
            kb_id=kb_id,
            query=query,
            top_k=top_k,
        )
        return {
            "success": True,
            "query": query,
            "total": len(incidents),
            "data": incidents,
        }
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": str(e),
            },
        )


@router.get("/kb/{kb_id}/context")
async def retrieve_context(
    kb_id: str,
    query: str = Query(...),
    top_k: int = Query(3, ge=1, le=20),
):
    """
    检索并生成可直接放入 LLM Prompt 的上下文文本
    """
    try:
        context = await knowledge_factory.service.retrieve_context(
            kb_id=kb_id,
            query=query,
            top_k=top_k,
        )
        return {
            "success": True,
            "context": context,
        }
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": str(e),
            },
        )


# ══════════════════════════════════════════════════════════
#  案例管理
# ══════════════════════════════════════════════════════════


@router.get("/kb/{kb_id}/incidents")
async def list_incidents(
    kb_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """分页列出知识库中的所有案例"""
    incidents, total = await knowledge_factory.incident_repository.list_by_kb(
        kb_id=kb_id,
        page=page,
        page_size=page_size,
    )
    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": incidents,
    }


@router.get("/incident/{incident_id}")
async def get_incident(incident_id: str):
    """获取单个案例详情"""
    incident = await knowledge_factory.incident_repository.get(incident_id)
    if incident is None:
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": "案例不存在"},
        )
    return {"success": True, "data": incident}


@router.delete("/incident/{incident_id}")
async def delete_incident(incident_id: str):
    """删除案例"""
    await knowledge_factory.incident_repository.delete(incident_id)
    return {"success": True, "message": "案例已删除"}


@router.get("/kb/{kb_id}/stats")
async def knowledge_base_stats(kb_id: str):
    """知识库统计信息"""
    incident_count = await knowledge_factory.incident_repository.count_by_kb(
        kb_id
    )
    document_count = await knowledge_factory.document_repository.count_by_kb(
        kb_id
    )
    return {
        "success": True,
        "kb_id": kb_id,
        "incident_count": incident_count,
        "document_count": document_count,
    }
