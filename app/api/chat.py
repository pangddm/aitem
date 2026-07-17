import os
import traceback
from fastapi import APIRouter, UploadFile, File, Form
from app.schemas.request_format import ChatRequest
from app.services.diagnosis_service import chat_with_agent
from app.document.parser import parse
from app.memory.container import memory_container
from app.memory.classes import MemorySource

router = APIRouter()
print("chat router loaded")

UPLOAD_DIR = "./data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/chat")
async def chat(request: ChatRequest):
    return await chat_with_agent(user_id=request.user_id, user_message=request.message)


@router.post("/chat_with_document")
async def chat_with_document(
    user_id: str = Form(...),
    message: str = Form(...),
    file: UploadFile = File(...),
):
    # =====================
    # 1. 保存文件
    # =====================
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # =====================
    # 2. 解析文档（图片由千问提取）
    # =====================
    try:
        chunks = parse(file_path)
        # 组装文档内容
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

    # =====================
    # 3. 文档中有用信息 → 存入长期记忆
    #    MemoryExtractor 会用 DeepSeek 自动判断
    #    哪些是值得记的有用信息，不会全量存
    # =====================
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
            # 记忆存储失败不影响主流程
            print(f"Document memory storage error: {e}")
            traceback.print_exc()

    # =====================
    # 4. 组装完整用户消息
    # =====================
    if document_content:
        full_message = f"""用户问题：{message}

---

参考文档内容（文档中的图片已使用视觉模型分析）：

{document_content}

---

请结合上述文档内容回答用户问题。"""
    else:
        full_message = message

    # =====================
    # 5. 调用 Agent（DeepSeek）
    # =====================
    response = await chat_with_agent(
        user_id=user_id,
        user_message=full_message,
    )

    return {"response": response}