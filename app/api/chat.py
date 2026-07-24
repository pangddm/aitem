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
    conv_id: str = Query(None),
    host_id: str = Query(None),
):
    """SSE 流式聊天——实时推送思考链、工具调用、答案，支持指定对话 ID 和主机"""

    # 解析主机连接信息
    host = port = ssh_user = ssh_pass = None
    if host_id:
        from app.api.conversation import get_host_by_id
        h = get_host_by_id(user_id, host_id)
        if h:
            host = h.get("host")
            port = h.get("port")
            ssh_user = h.get("username")
            ssh_pass = h.get("password")

    # 如果没有传 conv_id，自动创建一个新对话
    from app.api.conversation import save_message as save_conv_message
    actual_conv_id = conv_id
    if not actual_conv_id:
        import redis as _r
        actual_conv_id = str(uuid4())
        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        conv = {"id": actual_conv_id, "title": "新对话", "created_at": now, "updated_at": now}
        conv_r = _r.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            decode_responses=True,
        )
        ttl = int(os.getenv("REDIS_TTL", 86400 * 7))
        list_key = f"conv_list:{user_id}"
        data = conv_r.get(list_key)
        conversations = _json.loads(data) if data else []
        conversations.append(conv)
        conv_r.set(list_key, _json.dumps(conversations), ex=ttl)
        conv_r.set(f"conv_msgs:{actual_conv_id}", _json.dumps([]), ex=ttl)

    # 用于自动学习的数据收集
    auto_learn_data = {
        "task_plan": None,
        "execution_result": None,
        "observation": None,
    }

    # 思考链事件类型集合
    THINKING_EVENT_TYPES = {
        "reasoning", "task_plan", "risk_assessment", "validation",
        "tool_call", "tool_result", "observation", "retry_loop",
    }

    async def event_stream():
        nonlocal auto_learn_data
        try:
            memory_service = await get_memory_service()
            memories = await memory_service.search(owner=user_id, query=message)
        except Exception:
            memories = []

        knowledge_context = await _retrieve_knowledge_context(user_id, message)

        # 获取对话历史（用于 CommandRewriter 上下文理解）
        conversation_history = []
        if actual_conv_id:
            try:
                conv_r = _r.Redis(
                    host=os.getenv("REDIS_HOST", "localhost"),
                    port=int(os.getenv("REDIS_PORT", 6379)),
                    decode_responses=True,
                )
                msgs_data = conv_r.get(f"conv_msgs:{actual_conv_id}")
                if msgs_data:
                    all_msgs = _json.loads(msgs_data)
                    # 取最近 10 条消息作为上下文
                    conversation_history = all_msgs[-10:] if len(all_msgs) > 10 else all_msgs
            except Exception:
                pass

        # 发送 conv_id 给前端
        yield f"data: {_json.dumps({'type': 'conv_created', 'conv_id': actual_conv_id}, ensure_ascii=False)}\n\n"

        all_chunks = []
        thinking_chain = []  # 收集思考链数据
        try:
            workflow = AgentWorkflow()
            async for event in workflow.run_stream(
                user_id=user_id,
                user_message=message,
                memories=memories,
                knowledge_context=knowledge_context,
                host=host,
                port=port,
                username=ssh_user,
                password=ssh_pass,
            ):
                ct = event.get("content", "")
                if event.get("type") == "answer_chunk" and ct:
                    all_chunks.append(str(ct))

                # 收集思考链数据
                evt_type = event.get("type", "")
                if evt_type in THINKING_EVENT_TYPES:
                    thinking_chain.append({
                        "type": evt_type,
                        "content": event.get("content"),
                        "command": event.get("command"),
                        "result": event.get("result"),
                        "success": event.get("success"),
                    })

                # 收集自动学习所需数据
                if event.get("type") == "task_plan":
                    auto_learn_data["task_plan"] = event.get("content", {})
                elif event.get("type") == "tool_result":
                    auto_learn_data["execution_result"] = {
                        "success": True,
                        "command": event.get("command", ""),
                        "result": event.get("result", ""),
                    }
                elif event.get("type") == "observation":
                    auto_learn_data["observation"] = event.get("content", {})

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
            full_answer = "".join(all_chunks) if all_chunks else ""
            # 保存到对话存储（附带思考链）
            try:
                save_conv_message(actual_conv_id, "user", message, user_id)
                if full_answer:
                    save_conv_message(
                        actual_conv_id, "assistant", full_answer, user_id,
                        thinking_chain=thinking_chain if thinking_chain else None,
                    )
            except Exception:
                pass
            # 同时保持 SessionMemory 兼容
            try:
                from app.memory.short_term import SessionMemory
                sm = SessionMemory()
                history = sm.load(user_id)
                history.append({"role": "user", "content": message})
                if full_answer:
                    history.append({"role": "assistant", "content": full_answer})
                sm.save(user_id, history)
            except Exception:
                pass

            # 自动学习：后台沉淀知识
            if auto_learn_data["task_plan"] and auto_learn_data["execution_result"] and auto_learn_data["observation"]:
                try:
                    from app.knowledge.auto_learn import AutoLearner
                    learner = AutoLearner()
                    await learner.learn_and_store(
                        owner=user_id,
                        task_plan=auto_learn_data["task_plan"],
                        execution_result=auto_learn_data["execution_result"],
                        observation=auto_learn_data["observation"],
                    )
                except Exception as learn_err:
                    print(f"[AutoLearn] 后台学习异常: {learn_err}")

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

    # 使用新的 AgentWorkflow 替代旧的 chat_with_agent
    workflow = AgentWorkflow()
    result = await workflow.run(
        user_id=user_id,
        user_message=full_message,
    )
    return {"response": result.get("answer", "")}


@router.post("/chat/confirm")
async def confirm_command(
    confirm_id: int = Query(...),
    choice: str = Query(...),
):
    """用户确认或取消危险命令执行"""
    from app.llm.agents import _pending_confirmations
    entry = _pending_confirmations.get(confirm_id)
    if not entry:
        return {"success": False, "message": "确认请求不存在或已过期"}
    entry["choice"]["value"] = choice
    entry["event"].set()
    return {"success": True, "message": "确认已接收"}


@router.get("/chat/settings")
async def get_settings():
    """获取当前设置（测试模式等）"""
    from app.core.config import TEST_MODE
    return {
        "test_mode": TEST_MODE,
    }


@router.post("/chat/settings")
async def update_settings(
    test_mode: bool = Query(False),
):
    """
    更新设置
    test_mode: 测试模式开关，开启后跳过命令黑白名单
    """
    import os
    # 更新环境变量（运行时生效）
    os.environ["TEST_MODE"] = "true" if test_mode else "false"
    # 重新加载 config 模块
    import app.core.config as cfg
    cfg.TEST_MODE = test_mode
    return {
        "success": True,
        "test_mode": test_mode,
        "message": f"测试模式已{'开启' if test_mode else '关闭'}",
    }


@router.get("/chat/report/{conv_id}")
async def download_report(conv_id: str, user_id: str = Query(...)):
    """
    下载对话报告（Markdown 格式）
    从 Redis 读取对话数据，汇总为格式良好的 Markdown 报告文件
    """
    import redis as _r
    from fastapi.responses import Response
    from datetime import datetime
    
    conv_r = _r.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True,
    )
    
    try:
        # 从 Redis 获取对话消息
        msgs_data = conv_r.get(f"conv_msgs:{conv_id}")
        if not msgs_data:
            return {"success": False, "message": "对话不存在或为空"}
        
        messages = _json.loads(msgs_data)
        if not messages:
            return {"success": False, "message": "对话不存在或为空"}
        
        # 获取对话标题
        list_data = conv_r.get(f"conv_list:{user_id}")
        title = "Kubedoctor 报告"
        if list_data:
            conversations = _json.loads(list_data)
            for conv in conversations:
                if conv.get("id") == conv_id:
                    title = conv.get("title", "Kubedoctor 报告")
                    break
        
        # 构建格式良好的 Markdown 报告
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        safe_now = now.replace(":", "-").replace(" ", "_")
        
        md_lines = []
        # ── 报告头部 ──
        md_lines.append(f"# 📋 {title}")
        md_lines.append("")
        md_lines.append(f"| 项目 | 内容 |")
        md_lines.append(f"|------|------|")
        md_lines.append(f"| **生成时间** | {now} |")
        md_lines.append(f"| **用户** | {user_id} |")
        md_lines.append(f"| **消息数** | {len(messages)} |")
        md_lines.append(f"| **对话 ID** | `{conv_id}` |")
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")
        
        # ── 对话内容 ──
        for idx, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "") or "(无内容)"
            timestamp = msg.get("timestamp", "")
            
            if role == "user":
                md_lines.append(f"## 👤 用户")
            else:
                md_lines.append(f"## 🤖 Kubedoctor")
            
            if timestamp:
                try:
                    ts = timestamp[:19].replace("T", " ")
                except Exception:
                    ts = timestamp
                md_lines.append(f"")
                md_lines.append(f"> ⏰ {ts}")
            
            md_lines.append("")
            md_lines.append(content)
            md_lines.append("")
            
            # ── 思考链（可折叠） ──
            thinking_chain = msg.get("thinking_chain")
            if thinking_chain and len(thinking_chain) > 0:
                md_lines.append("<details>")
                md_lines.append("<summary>💭 思考链</summary>")
                md_lines.append("")
                
                for item in thinking_chain:
                    item_type = item.get("type", "")
                    item_content = item.get("content", "")
                    item_command = item.get("command", "")
                    item_result = item.get("result", "")
                    
                    # 根据类型确定标题
                    type_titles = {
                        "reasoning": "💭 思考",
                        "task_plan": "📋 任务计划",
                        "risk_assessment": "⚠️ 风险评估",
                        "validation": "✅ 命令校验",
                        "tool_call": "🔧 执行命令",
                        "tool_result": "📋 执行结果",
                        "observation": "👁️ 结果观察",
                        "retry_loop": "🔄 重试",
                        "auto_fix": "🤖 自动修复",
                        "choice_applied": "✅ 已选择方案",
                    }
                    item_title = type_titles.get(item_type, f"📌 {item_type}")
                    
                    md_lines.append(f"#### {item_title}")
                    md_lines.append("")
                    
                    if item_command:
                        md_lines.append("**命令:**")
                        md_lines.append(f"```bash")
                        md_lines.append(str(item_command))
                        md_lines.append(f"```")
                        md_lines.append("")
                    
                    if item_content:
                        # 尝试格式化 JSON 内容
                        content_str = str(item_content)
                        try:
                            parsed = _json.loads(content_str)
                            content_str = _json.dumps(parsed, ensure_ascii=False, indent=2)
                            md_lines.append(f"```json")
                            md_lines.append(content_str[:3000])
                            md_lines.append(f"```")
                        except Exception:
                            md_lines.append(f"```")
                            md_lines.append(content_str[:3000])
                            md_lines.append(f"```")
                        md_lines.append("")
                    
                    if item_result:
                        md_lines.append("**输出:**")
                        md_lines.append(f"```")
                        md_lines.append(str(item_result)[:3000])
                        md_lines.append(f"```")
                        md_lines.append("")
                
                md_lines.append("</details>")
                md_lines.append("")
            
            md_lines.append("---")
            md_lines.append("")
        
        # ── 报告尾部 ──
        md_lines.append("")
        md_lines.append(f"*本报告由 Kubedoctor 自动生成于 {now}*")
        md_lines.append("")
        
        report_content = "\n".join(md_lines)
        
        # 返回 Markdown 文件
        # 文件名只保留 ASCII 安全字符，避免 Content-Disposition header 编码错误
        import re as _re
        safe_title = _re.sub(r'[^\w\-]', '_', title)[:30]
        filename = f"Kubedoctor_{safe_title}_{safe_now}.md"
        # 使用 RFC 5987 编码处理非 ASCII 文件名
        from urllib.parse import quote
        encoded_filename = quote(filename)
        return Response(
            content=report_content,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            },
        )
    except Exception as e:
        traceback.print_exc()
        return {"success": False, "message": f"生成报告失败: {str(e)}"}
