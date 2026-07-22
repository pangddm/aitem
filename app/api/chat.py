import os
import json as _json
import traceback
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse

from app.schemas.request_format import ChatRequest
from app.services.diagnosis_service import chat_with_agent, get_memory_service, _retrieve_knowledge_context
from app.document.parser import parse
from app.memory.container import memory_container
from app.memory.classes import MemorySource
from app.knowledge.factory import knowledge_factory
from app.llm.agents import AgentWorkflow

router = APIRouter()
print("chat router loaded")

UPLOAD_DIR = "./data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


async def _ingest_to_knowledge_base(owner: str, file_path: str):
    """后台任务：将聊天附件导入用户的知识库"""
    try:
        kbs = await knowledge_factory.kb_repository.list_by_owner(owner)
        if kbs:
            kb_id = kbs[0].id
        else:
            from app.knowledge.models import KnowledgeBase
            from datetime import datetime

            kb_id = str(uuid4())
            now = datetime.utcnow()
            kb = KnowledgeBase(
                id=kb_id,
                owner=owner,
                name="聊天文档",
                description="自动从聊天附件中收集的文档知识",
                created_at=now,
                updated_at=now,
            )
            await knowledge_factory.kb_repository.create(kb)

        await knowledge_factory.service.upload_document(
            kb_id=kb_id,
            file_path=file_path,
            owner=owner,
        )
        print(f"[RAG] 聊天附件已入库: {file_path} → kb={kb_id}")
    except Exception as e:
        print(f"[RAG] 聊天附件入库失败: {e}")
        traceback.print_exc()


@router.post("/chat")
async def chat(request: ChatRequest):
    return await chat_with_agent(user_id=request.user_id, user_message=request.message)


@router.get("/chat/stream")
async def chat_stream(
    user_id: str = Query(...),
    message: str = Query(...),
):
    """SSE 流式聊天——实时推送思考链、工具调用、答案"""

    async def event_stream():
        try:
            memory_service = await get_memory_service()
            memories = await memory_service.search(owner=user_id, query=message)
        except Exception:
            memories = []

        knowledge_context = await _retrieve_knowledge_context(user_id, message)

        all_chunks = []
        try:
            workflow = AgentWorkflow()
            async for event in workflow.run_stream(
                user_id=user_id,
                user_message=message,
                memories=memories,
                knowledge_context=knowledge_context,
            ):
                ct = event.get("content", "")
                if event.get("type") == "answer_chunk" and ct:
                    all_chunks.append(str(ct))
                try:
                    yield f"data: {_json.dumps(event, ensure_ascii=False)}\n\n"
                except GeneratorExit:
                    return
        except Exception as e:
            print(f"[SSE] Stream error: {type(e).__name__}: {e}")
            traceback.print_exc()
            try:
                yield f"data: {_json.dumps({'type': 'error', 'content': str(e)[:200]}, ensure_ascii=False)}\n\n"
            except Exception:
                pass
        finally:
            try:
                from app.memory.short_term import SessionMemory
                sm = SessionMemory()
                history = sm.load(user_id)
                history.append({"role": "user", "content": message})
                if all_chunks:
                    history.append({"role": "assistant", "content": "".join(all_chunks)})
                sm.save(user_id, history)
            except Exception:
                pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat_with_document")
async def chat_with_document(
    background_tasks: BackgroundTasks,
    user_id: str = Form(...),
    message: str = Form(...),
    file: UploadFile = File(...),
):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    background_tasks.add_task(
        _ingest_to_knowledge_base,
        owner=user_id,
        file_path=file_path,
    )

    try:
        chunks = parse(file_path)
        doc_lines = []
        for chunk in chunks:
            ctype = chunk.get("type", "text")
            ccontent = chunk.get("content", "")
            if ctype == "text":
                doc_lines.append(f"[文本] {ccontent}")
            elif ctype == "image":
                doc_lines.append(f"[图片描述] {ccontent}")
        document_content = "\n\n".join(doc_lines)
    except Exception as e:
        traceback.print_exc()
        document_content = ""
        chunks = []

    if chunks:
        try:
            memory_messages = []
            for chunk in chunks:
                ctype = chunk.get("type", "text")
                ccontent = chunk.get("content", "")
                memory_messages.append({
                    "role": "user",
                    "content": (
                        f"文档来源: {file_path}\n"
                        f"内容类型: {ctype}\n"
                        f"内容: {ccontent}"
                    ),
                })
            memory_service = memory_container.create_service()
            await memory_service.process(
                owner=user_id,
                messages=memory_messages,
                source=MemorySource.DOCUMENT,
            )
        except Exception as e:
            print(f"Document memory storage error: {e}")
            traceback.print_exc()

    if document_content:
        full_message = f"""用户问题：{message}

---

参考文档内容（文档中的图片已使用视觉模型分析）：

{document_content}

---

请结合上述文档内容回答用户问题。"""
    else:
        full_message = message

    response = await chat_with_agent(
        user_id=user_id,
        user_message=full_message,
    )

    return {"response": response}