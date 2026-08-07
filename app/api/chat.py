import os
import asyncio
import json as _json
import traceback
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse

from app.schemas.request_format import ChatRequest
from app.services.diagnosis_service import chat_with_agent, get_memory_service, _retrieve_knowledge_context, _retrieve_graph_context
from app.document.parser import parse
from app.memory.container import memory_container
from app.memory.classes import MemorySource
from app.knowledge.factory import knowledge_factory
from app.llm.agents import AgentWorkflow

router = APIRouter()

UPLOAD_DIR = "./data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


CHAT_KB_NAME = "聊天文档"  # 聊天文档专用的知识库名称


async def _web_search(query: str, top: int = 5) -> str:
    """免费联网搜索：DuckDuckGo Lite（网页结果）+ DuckDuckGo Instant Answer（定义/摘要）。

    无 API key、短超时、失败静默降级；搜索不到时返回空字符串，不阻塞主流程。
    """
    import asyncio
    import httpx
    import re
    from urllib.parse import urlparse, parse_qs, unquote

    _UA = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        )
    }

    async def _lite() -> list:
        parts: list[str] = []
        async with httpx.AsyncClient(timeout=6.0, headers=_UA, follow_redirects=True) as client:
            r = await client.get("https://lite.duckduckgo.com/lite/", params={"q": query})
        html = r.text
        links = re.findall(
            r"<a[^>]*href=\"([^\"]+)\"[^>]*class='result-link'[^>]*>(.*?)</a>", html, re.S,
        )
        snippets = re.findall(r"<td[^>]*class='result-snippet'[^>]*>(.*?)</td>", html, re.S)

        def _real(h: str) -> str:
            q = parse_qs(urlparse(h).query)
            u = q.get("uddg", [None])[0]
            return unquote(u) if u else h

        for i, (href, title_html) in enumerate(links[:top]):
            title = re.sub(r"<[^>]+>", "", title_html).strip()
            sn = re.sub(r"<[^>]+>", "", snippets[i]).strip() if i < len(snippets) else ""
            if title:
                parts.append(f"{i + 1}. {title} — {sn}（来源：{_real(href)}）")
        return parts

    async def _instant() -> list:
        parts: list[str] = []
        async with httpx.AsyncClient(timeout=6.0, headers=_UA) as client:
            r = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            )
        data = r.json()
        if data.get("AbstractText"):
            parts.append(f"- 摘要：{data['AbstractText']}")
        if data.get("AbstractURL"):
            parts.append(f"- 出处：{data['AbstractURL']}")
        for topic in data.get("RelatedTopics", [])[:4]:
            if isinstance(topic, dict):
                text = topic.get("Text") or topic.get("Title")
                if text:
                    parts.append(f"- {text}")
        return parts

    out: list[str] = []
    try:
        lite_res, instant_res = await asyncio.gather(_lite(), _instant(), return_exceptions=True)
        for res in (lite_res, instant_res):
            if isinstance(res, list):
                out.extend(res)
    except Exception as e:
        print(f"[WebSearch] 搜索失败: {type(e).__name__}: {e}")

    uniq: list[str] = []
    seen: set[str] = set()
    for p2 in out:
        if p2 not in seen:
            seen.add(p2)
            uniq.append(p2)
    return "\n".join(uniq[:top])

async def _get_or_create_chat_kb(owner: str) -> str:
    """获取或创建用户的'聊天文档'知识库，返回 kb_id"""
    from app.knowledge.models import KnowledgeBase
    from datetime import datetime

    # 查找用户所有知识库，找名为"聊天文档"的
    kbs = await knowledge_factory.kb_repository.list_by_owner(owner)
    for kb in kbs:
        if kb.name == CHAT_KB_NAME:
            return kb.id

    # 没找到，创建一个
    kb_id = str(uuid4())
    now = datetime.utcnow()
    kb = KnowledgeBase(
        id=kb_id,
        owner=owner,
        name=CHAT_KB_NAME,
        description="自动从聊天附件中收集的文档知识",
        created_at=now,
        updated_at=now,
    )
    await knowledge_factory.kb_repository.create(kb)
    print(f"[RAG] 创建'聊天文档'知识库: kb={kb_id}")
    return kb_id


async def _ingest_to_knowledge_base(owner: str, file_path: str):
    """后台任务：将聊天附件导入'聊天文档'知识库（与其他知识库隔离）"""
    try:
        kb_id = await _get_or_create_chat_kb(owner)

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
    from app.llm.client import reset_model_state
    reset_model_state()
    return await chat_with_agent(user_id=request.user_id, user_message=request.message)


@router.get("/chat/stream")
async def chat_stream(
    user_id: str = Query(...),
    message: str = Query(...),
    conv_id: str = Query(None),
    host_id: str = Query(None),
    web_search: bool = Query(False),
):
    """SSE 流式聊天——实时推送思考链、工具调用、答案，支持指定对话 ID 和主机"""

    # 解析主机连接信息
    host = port = ssh_user = ssh_pass = None
    if host_id:
        from app.api.conversation import get_host_by_id
        h = await get_host_by_id(user_id, host_id)
        if h:
            host = h.get("host")
            port = h.get("port")
            ssh_user = h.get("username")
            ssh_pass = h.get("password")

    # 如果没有传 conv_id，自动创建一个新对话（持久化到 PostgreSQL）
    from app.api.conversation import save_message as save_conv_message
    from app.db.repository.conversation_repository import conversation_repo
    actual_conv_id = conv_id
    if not actual_conv_id:
        conv = await conversation_repo.create(user_id, "新对话")
        actual_conv_id = conv["id"]

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
        "answer_reasoning", "command_rewritten",
    }
    # 整体看门狗：整条流式流程最长等待时间，超时则终止避免无限挂起
    OVERALL_STREAM_TIMEOUT = 300

    async def event_stream():
        nonlocal auto_learn_data
        from app.llm.client import reset_model_state
        reset_model_state()
        try:
            memory_service = await get_memory_service()
            memories = await memory_service.search(owner=user_id, query=message)
            print(f"[Request] user={user_id} web_search={web_search} message={message}")
        except Exception:
            memories = []
            print("[Request] 长期记忆检索失败")
        print(f"[Memory] 检索到 {len(memories)} 条长期记忆")

        knowledge_context = await _retrieve_knowledge_context(user_id, message)
        print(f"[RAG] 知识库上下文 {len(knowledge_context)} 字符")

        # 注入图拓扑/审计参考（方案A：图仅作提示，事实以 kubectl 实测为准）
        graph_context = await _retrieve_graph_context(user_id, message)
        if graph_context:
            knowledge_context = "【集群拓扑图参考（缓存提示，须用 kubectl 复核）】\n" + graph_context + "\n\n" + knowledge_context
            print(f"[Graph] 注入拓扑上下文 {len(graph_context)} 字符")

        # 联网搜索：把实时搜索结果注入上下文（不阻塞、失败静默降级）
        print(f"[WebSearch] 开关={web_search}")
        web_context = ""
        if web_search:
            try:
                yield f"data: {_json.dumps({'type': 'web_search', 'query': message, 'content': '正在联网搜索...'}, ensure_ascii=False)}\n\n"
            except Exception:
                pass
            print(f"[WebSearch] 开始实时搜索: {message}")
            web_info = await _web_search(message)
            web_context = web_info or ""
            print(f"[WebSearch] 返回 {len(web_context)} 字符（作为独立实时上下文注入）")
            try:
                yield f"data: {_json.dumps({'type': 'web_search', 'query': message, 'content': web_info or '(无结果)'}, ensure_ascii=False)}\n\n"
            except Exception:
                pass
        print(f"[Context] 注入 AI 的上下文共 {len(knowledge_context)} 字符，实时联网 {len(web_context)} 字符")

        # 获取对话历史（用于 CommandRewriter 上下文理解）
        conversation_history = []
        if actual_conv_id:
            try:
                all_msgs = await conversation_repo.list_messages(actual_conv_id)
                # 取最近 10 条消息作为上下文
                conversation_history = all_msgs[-10:] if len(all_msgs) > 10 else all_msgs
            except Exception:
                pass
        
        # 新对话不应该有跨对话历史，保持 conversation_history 为空
        # （旧代码从 SessionMemory 获取跨对话历史，导致新对话有旧对话记忆的 bug）

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
                web_context=web_context,
                host=host,
                port=port,
                username=ssh_user,
                password=ssh_pass,
                conversation_history=conversation_history,
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
                        "agent": event.get("agent", ""),
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
            # 发送结束事件
            try:
                yield f"data: {_json.dumps({'type': 'done', 'content': ''}, ensure_ascii=False)}\n\n"
            except Exception:
                pass

            full_answer = "".join(all_chunks) if all_chunks else ""
            # 保存到对话存储（附带思考链）
            try:
                await save_conv_message(actual_conv_id, "user", message, user_id)
                if full_answer:
                    await save_conv_message(
                        actual_conv_id, "assistant", full_answer, user_id,
                        thinking_chain=thinking_chain if thinking_chain else None,
                    )
            except Exception as save_err:
                print(f"[SSE] Save message error: {type(save_err).__name__}: {save_err}")
                traceback.print_exc()
            # 不再保存到 SessionMemory，避免跨对话污染
            # 对话历史已通过 conv_msgs:{actual_conv_id} 按对话隔离

            # 长期记忆：后台异步沉淀本次对话（不阻塞 SSE 流的结束）
            async def _run_memory():
                try:
                    msgs = [{"role": "user", "content": message}]
                    if full_answer:
                        msgs.append({"role": "assistant", "content": full_answer})
                    service = memory_container.create_service()
                    await service.process(
                        owner=user_id,
                        messages=msgs,
                        source=MemorySource.CHAT,
                    )
                except Exception as mem_err:
                    print(f"[Memory] 对话长期记忆存储失败: {type(mem_err).__name__}: {mem_err}")
            asyncio.create_task(_run_memory())

            # 自动学习：作为后台任务异步沉淀知识，不阻塞 SSE 流的结束，
            # 避免"回复已完成但光标还在闪"的问题
            if auto_learn_data["task_plan"] and auto_learn_data["execution_result"] and auto_learn_data["observation"]:
                async def _run_auto_learn():
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
                asyncio.create_task(_run_auto_learn())

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_workflow_events(
    user_id: str,
    user_message: str,
    actual_conv_id: str,
    memories: list,
    knowledge_context: str,
    conversation_history: list,
    user_log_text: str = None,
):
    """运行 AgentWorkflow.run_stream，转发事件并保存会话/记忆/自动学习。

    以 dict 事件迭代输出，由调用方序列化为 SSE；结束时发送 done 事件。
    """
    from app.api.conversation import save_message as save_conv_message

    THINKING_EVENT_TYPES = {
        "reasoning", "task_plan", "risk_assessment", "validation",
        "tool_call", "tool_result", "observation", "retry_loop",
        "answer_reasoning", "command_rewritten",
    }
    all_chunks = []
    thinking_chain = []
    auto_learn_data = {"task_plan": None, "execution_result": None, "observation": None}
    try:
        workflow = AgentWorkflow()
        agen = workflow.run_stream(
            user_id=user_id,
            user_message=user_message,
            memories=memories,
            knowledge_context=knowledge_context,
            conversation_history=conversation_history,
        )
        loop = asyncio.get_running_loop()
        deadline = loop.time() + OVERALL_STREAM_TIMEOUT
        timed_out = False
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                timed_out = True
                break
            try:
                event = await asyncio.wait_for(agen.__anext__(), timeout=remaining)
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError:
                timed_out = True
                break

            ct = event.get("content", "")
            if event.get("type") == "answer_chunk" and ct:
                all_chunks.append(str(ct))

            evt_type = event.get("type", "")
            if evt_type in THINKING_EVENT_TYPES:
                thinking_chain.append({
                    "type": evt_type,
                    "content": event.get("content"),
                    "command": event.get("command"),
                    "result": event.get("result"),
                    "success": event.get("success"),
                    "agent": event.get("agent", ""),
                })

            if evt_type == "task_plan":
                auto_learn_data["task_plan"] = event.get("content", {})
            elif evt_type == "tool_result":
                auto_learn_data["execution_result"] = {
                    "success": True,
                    "command": event.get("command", ""),
                    "result": event.get("result", ""),
                }
            elif evt_type == "observation":
                auto_learn_data["observation"] = event.get("content", {})

            yield event

        if timed_out:
            try:
                await agen.aclose()
            except Exception:
                pass
            print("[SSE] 整体流式流程超时，强制终止")
            yield {"type": "error", "content": "⚠️ AI 处理超时（长时间无响应，通常是 LLM 服务不可达或网络问题）。请稍后重试，或检查 LLM API 配置。"}
    except Exception as e:
        print(f"[SSE] Stream error: {type(e).__name__}: {e}")
        traceback.print_exc()
        try:
            yield {"type": "error", "content": str(e)[:200]}
        except Exception:
            pass
    finally:
        try:
            yield {"type": "done", "content": ""}
        except Exception:
            pass

        full_answer = "".join(all_chunks) if all_chunks else ""
        try:
            await save_conv_message(
                actual_conv_id, "user", user_log_text or user_message, user_id,
            )
            if full_answer:
                await save_conv_message(
                    actual_conv_id, "assistant", full_answer, user_id,
                    thinking_chain=thinking_chain if thinking_chain else None,
                )
        except Exception as save_err:
            print(f"[SSE] Save message error: {type(save_err).__name__}: {save_err}")
            traceback.print_exc()

        async def _run_memory():
            try:
                msgs = [{"role": "user", "content": user_log_text or user_message}]
                if full_answer:
                    msgs.append({"role": "assistant", "content": full_answer})
                service = memory_container.create_service()
                await service.process(owner=user_id, messages=msgs, source=MemorySource.CHAT)
            except Exception as mem_err:
                print(f"[Memory] 对话长期记忆存储失败: {type(mem_err).__name__}: {mem_err}")
        asyncio.create_task(_run_memory())

        if auto_learn_data["task_plan"] and auto_learn_data["execution_result"] and auto_learn_data["observation"]:
            async def _run_auto_learn():
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
            asyncio.create_task(_run_auto_learn())


@router.post("/chat_with_document")
async def chat_with_document(
    background_tasks: BackgroundTasks,
    user_id: str = Form(...),
    message: str = Form(...),
    file: UploadFile = File(...),
):
    """上传附件的聊天：解析文档并注入上下文，走与普通聊天一致的流式 SSE（思考链 + 流式回复）"""
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

    if document_content:
        full_message = f"""用户问题：{message}

---

参考文档内容（文档中的图片已使用视觉模型分析）：

{document_content}

---

请结合上述文档内容回答用户问题。"""
    else:
        full_message = message

    # 创建对话记录
    from app.db.repository.conversation_repository import conversation_repo
    conv = await conversation_repo.create(user_id, "文档对话")
    actual_conv_id = conv["id"]

    async def event_stream():
        from app.llm.client import reset_model_state
        reset_model_state()
        try:
            memory_service = await get_memory_service()
            memories = await memory_service.search(owner=user_id, query=message)
        except Exception:
            memories = []
            print("[Request] 长期记忆检索失败")

        knowledge_context = await _retrieve_knowledge_context(user_id, message)

        # 注入图拓扑/审计参考
        graph_context = await _retrieve_graph_context(user_id, message)
        if graph_context:
            knowledge_context = "【集群拓扑图参考（缓存提示，须用 kubectl 复核）】\n" + graph_context + "\n\n" + knowledge_context

        # 注入用户上传的文档内容（供直接回答）
        if document_content:
            knowledge_context = f"【用户上传文档内容（供直接回答）】\n{document_content}\n\n" + knowledge_context

        # 对话历史
        conversation_history = []
        try:
            all_msgs = await conversation_repo.list_messages(actual_conv_id)
            conversation_history = all_msgs[-10:] if len(all_msgs) > 10 else all_msgs
        except Exception:
            pass

        yield f"data: {_json.dumps({'type': 'conv_created', 'conv_id': actual_conv_id}, ensure_ascii=False)}\n\n"

        async for event in _stream_workflow_events(
            user_id=user_id,
            user_message=full_message,
            actual_conv_id=actual_conv_id,
            memories=memories,
            knowledge_context=knowledge_context,
            conversation_history=conversation_history,
            user_log_text=message,
        ):
            try:
                yield f"data: {_json.dumps(event, ensure_ascii=False)}\n\n"
            except GeneratorExit:
                return

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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
    从 PostgreSQL 读取对话数据，汇总为格式良好的 Markdown 报告文件
    """
    from fastapi.responses import Response
    from datetime import datetime
    from app.db.repository.conversation_repository import conversation_repo
    
    try:
        # 从 PostgreSQL 获取对话消息
        messages = await conversation_repo.list_messages(conv_id)
        if not messages:
            return {"success": False, "message": "对话不存在或为空"}
        
        # 获取对话标题
        conv_info = await conversation_repo.get(conv_id)
        title = conv_info["title"] if conv_info else "Kubedoctor 报告"
        
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
        
        # 转为 Word 文档
        from app.services.docx_export import markdown_to_docx
        docx_buf = markdown_to_docx(report_content)

        # 文件名只保留 ASCII 安全字符，避免 Content-Disposition header 编码错误
        import re as _re
        safe_title = _re.sub(r'[^\w\-]', '_', title)[:30]
        filename = f"Kubedoctor_{safe_title}_{safe_now}.docx"
        # 使用 RFC 5987 编码处理非 ASCII 文件名
        from urllib.parse import quote
        encoded_filename = quote(filename)
        return Response(
            content=docx_buf.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            },
        )
    except Exception as e:
        traceback.print_exc()
        return {"success": False, "message": f"生成报告失败: {str(e)}"}

