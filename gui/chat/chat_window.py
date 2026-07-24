import os
from html import escape

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTextBrowser,
    QLineEdit,
    QPushButton,
    QLabel,
    QHBoxLayout,
    QFileDialog,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer, QThread, QSettings

from api import chat, chat_with_document
from knowledge.kb_window import KnowledgeWindow
from .workers import ChatWorker, VoiceWorker, StreamChatWorker
from .cot_html import build_cot_html


class ChatWindow(QWidget):

    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.setWindowTitle("Kubedoctor")
        self.resize(1080, 780)
        self.setStyleSheet("background: #0f172a; color: #e2e8f0;")
        self.messages = []
        self.is_recording = False
        self.selected_file = None
        self._cot_expanded = set()
        self._settings = QSettings("Kubedoctor", "ChatHistory")
        self._load_history()
        self.init_ui()
        if self.messages:
            self._render_history()

    def showEvent(self, event):
        super().showEvent(event)
        if self.messages:
            tc = self.history.textCursor()
            tc.movePosition(tc.MoveOperation.End)
            self.history.setTextCursor(tc)

    def _load_history(self):
        """从本地加载聊天历史"""
        import json as _json
        raw = self._settings.value(f"history/{self.user_id}", "")
        if raw:
            try:
                self.messages = _json.loads(raw)
                self.messages = self.messages[-30:]
            except Exception:
                self.messages = []

    def _save_history(self):
        """保存聊天历史到本地"""
        import json as _json
        if self.messages:
            save = []
            for m in self.messages[-30:]:
                m2 = dict(m)
                m2.pop("visible_lines", None)
                m2.pop("expanded", None)
                save.append(m2)
            self._settings.setValue(f"history/{self.user_id}", _json.dumps(save, ensure_ascii=False))
            self._settings.sync()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(12)

        # ── Header ──
        header = QHBoxLayout()
        title = QLabel("Kubedoctor")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #f8fafc;")
        header.addWidget(title)

        self.kb_btn = QPushButton("📚 知识库")
        self.kb_btn.setStyleSheet(
            """
            QPushButton {
                background: #1f2937;
                color: #e2e8f0;
                border: 1px solid #374151;
                border-radius: 10px;
                padding: 6px 14px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #374151;
                border-color: #10b981;
            }
            """
        )
        self.kb_btn.clicked.connect(self._open_knowledge_base)
        header.addWidget(self.kb_btn)

        # 测试模式开关
        self.test_mode_btn = QPushButton("🧪 测试模式: 关")
        self.test_mode_btn.setCheckable(True)
        self.test_mode_btn.setStyleSheet(
            """
            QPushButton {
                background: #1f2937;
                color: #e2e8f0;
                border: 1px solid #374151;
                border-radius: 10px;
                padding: 6px 14px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #374151;
                border-color: #f59e0b;
            }
            QPushButton:checked {
                background: #78350f;
                border-color: #f59e0b;
                color: #fbbf24;
            }
            """
        )
        self.test_mode_btn.clicked.connect(self._toggle_test_mode)
        header.addWidget(self.test_mode_btn)

        header.addStretch()

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        header.addWidget(self.status_label)
        main_layout.addLayout(header)

        # ── Chat History ──
        self.history = QTextBrowser()
        self.history.setReadOnly(True)
        self.history.setAcceptRichText(True)
        self.history.setOpenExternalLinks(False)
        self.history.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        self.history.setStyleSheet(
            "QTextBrowser {"
            "  background: #111827; border: 1px solid #1f2937; border-radius: 16px;"
            "  padding: 10px; color: #f8fafc;"
            "}"
            "QScrollBar:vertical {"
            "  width: 12px; background: #0f172a; border: none;"
            "}"
            "QScrollBar::handle:vertical {"
            "  background: #64748b; border-radius: 6px; min-height: 40px;"
            "}"
            "QScrollBar::handle:vertical:hover {"
            "  background: #94a3b8;"
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
            "  height: 0px;"
            "}"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {"
            "  background: none;"
            "}"
        )
        self.history.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.history.anchorClicked.connect(self._on_cot_toggle)
        main_layout.addWidget(self.history, 1)

        # ── 附件标签 ──
        self.file_tag_layout = QHBoxLayout()
        self.file_tag_layout.setContentsMargins(4, 0, 4, 0)
        self.file_tag_layout.setSpacing(6)
        self.file_tag_label = QLabel()
        self.file_tag_label.setVisible(False)
        self.file_tag_label.setStyleSheet(
            "background: #1e293b; color: #e2e8f0; border: 1px solid #334155; "
            "border-radius: 12px; padding: 4px 12px; font-size: 13px;"
        )
        self.cancel_file_btn = QPushButton("✕")
        self.cancel_file_btn.setFixedSize(24, 24)
        self.cancel_file_btn.setVisible(False)
        self.cancel_file_btn.setStyleSheet(
            "background: transparent; color: #94a3b8; border: none; font-size: 14px; font-weight: bold;"
        )
        self.cancel_file_btn.clicked.connect(self._cancel_file)
        self.file_tag_layout.addWidget(self.file_tag_label)
        self.file_tag_layout.addWidget(self.cancel_file_btn)
        self.file_tag_layout.addStretch()
        main_layout.addLayout(self.file_tag_layout)

        # ── Composer ──
        composer = QHBoxLayout()
        composer.setContentsMargins(0, 0, 0, 0)
        composer.setSpacing(8)

        # 附件按钮
        self.attach_btn = QPushButton("📎")
        self.attach_btn.setToolTip("添加文档一并提问")
        self.attach_btn.setFixedSize(42, 42)
        self.attach_btn.setStyleSheet(self._tool_button_style())
        self.attach_btn.clicked.connect(self.attach_file)

        # 语音按钮
        self.voice_btn = QPushButton("🎤")
        self.voice_btn.setToolTip("语音输入")
        self.voice_btn.setFixedSize(42, 42)
        self.voice_btn.setStyleSheet(self._tool_button_style())
        self.voice_btn.clicked.connect(self.toggle_voice_input)

        # 输入框
        self.input = QLineEdit()
        self.input.setPlaceholderText("请输入问题...")
        self.input.setStyleSheet(
            "background: #1f2937; border: 1px solid #374151; border-radius: 999px; padding: 12px 16px; color: #f9fafb;"
        )
        self.input.returnPressed.connect(self.send)

        # 发送按钮
        self.send_btn = QPushButton("发送")
        self.send_btn.setStyleSheet(
            """
            QPushButton {
                background: #10a37f;
                color: white;
                border: none;
                border-radius: 999px;
                padding: 10px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #0d8a6a;
            }
            QPushButton:disabled {
                background: #4b5563;
                color: #d1d5db;
            }
            """
        )
        self.send_btn.clicked.connect(self.send)

        # 停止按钮（流式时显示）
        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.setVisible(False)
        self.stop_btn.setStyleSheet(
            """
            QPushButton {
                background: #dc2626; color: white; border: none;
                border-radius: 999px; padding: 10px 16px; font-weight: 600;
            }
            QPushButton:hover { background: #b91c1c; }
            """
        )
        self.stop_btn.clicked.connect(self._stop_streaming)

        composer.addWidget(self.attach_btn)
        composer.addWidget(self.voice_btn)
        composer.addWidget(self.input, 1)
        composer.addWidget(self.stop_btn)
        composer.addWidget(self.send_btn)
        main_layout.addLayout(composer)

        self.setLayout(main_layout)

    def _tool_button_style(self):
        return """
            QPushButton {
                background: #1f2937;
                border: 1px solid #374151;
                border-radius: 21px;
                font-size: 18px;
            }
            QPushButton:hover {
                background: #374151;
                border-color: #10a37f;
            }
            QPushButton:pressed {
                background: #111827;
            }
        """

    # ───────────────────────────────
    #  测试模式开关
    # ───────────────────────────────
    def _toggle_test_mode(self):
        """切换测试模式"""
        import requests
        is_checked = self.test_mode_btn.isChecked()
        try:
            resp = requests.post(
                f"http://localhost:8000/chat/settings",
                params={"test_mode": is_checked},
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    mode_text = "开" if is_checked else "关"
                    self.test_mode_btn.setText(f"🧪 测试模式: {mode_text}")
                    self.status_label.setText(f"测试模式已{'开启' if is_checked else '关闭'} — 命令黑白名单已{'跳过' if is_checked else '启用'}")
                    QTimer.singleShot(3000, lambda: self.status_label.setText("就绪"))
                else:
                    self.test_mode_btn.setChecked(not is_checked)
                    self.status_label.setText("❌ 切换失败")
            else:
                self.test_mode_btn.setChecked(not is_checked)
                self.status_label.setText("❌ 切换失败")
        except Exception as e:
            self.test_mode_btn.setChecked(not is_checked)
            self.status_label.setText(f"❌ 连接失败: {e}")

    # ───────────────────────────────
    #  知识库管理（打开独立窗口）
    # ───────────────────────────────
    def _open_knowledge_base(self):
        self.kb_window = KnowledgeWindow(owner=self.user_id)
        self.kb_window.show()

    # ───────────────────────────────
    #  文件选择（选择后暂存，发送时一起提交）
    # ───────────────────────────────
    def attach_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文档一并提问",
            "",
            "文档 (*.docx *.png *.jpg *.jpeg);;Word文档 (*.docx);;图片 (*.png *.jpg *.jpeg);;所有文件 (*)"
        )
        if not file_path:
            return

        self.selected_file = file_path
        filename = os.path.basename(file_path)
        self.file_tag_label.setText(f"📎 {filename}")
        self.file_tag_label.setVisible(True)
        self.cancel_file_btn.setVisible(True)

    def _cancel_file(self):
        self.selected_file = None
        self.file_tag_label.setVisible(False)
        self.cancel_file_btn.setVisible(False)

    # ───────────────────────────────
    #  语音输入（支持开始/停止）
    # ───────────────────────────────
    def toggle_voice_input(self):
        if not self.is_recording:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        self.is_recording = True
        self.voice_btn.setStyleSheet(
            self._tool_button_style().replace("#1f2937", "#dc2626")
            .replace("#374151", "#dc2626")
        )
        self.voice_btn.setText("⏹")
        self.voice_btn.setToolTip("停止录音")
        self.status_label.setText("🎤 录音中，点击 ⏹ 结束...")

        self.voice_worker = VoiceWorker()
        self.voice_thread = QThread(self)
        self.voice_worker.moveToThread(self.voice_thread)
        self.voice_thread.started.connect(self.voice_worker.run)
        self.voice_worker.result_ready.connect(self._on_voice_result)
        self.voice_worker.result_ready.connect(self.voice_thread.quit)
        self.voice_thread.finished.connect(self._cleanup_voice_thread)
        self.voice_thread.start()

    def _stop_recording(self):
        if hasattr(self, 'voice_worker') and self.voice_worker:
            self.voice_worker.stop()
        self.status_label.setText("🎤 正在识别...")

    def _on_voice_result(self, text):
        if text and text.startswith("[ERROR]"):
            self.status_label.setText(f"❌ {text[7:]}")
            self._reset_voice_button(keep_status=True)
        elif text:
            self.input.setText(text)
            self.status_label.setText("🎤 识别完成")
            self._reset_voice_button()
        else:
            self.status_label.setText("🎤 未识别到语音")
            self._reset_voice_button()

    def _reset_voice_button(self, keep_status=False):
        self.is_recording = False
        self.voice_btn.setText("🎤")
        self.voice_btn.setToolTip("语音输入")
        self.voice_btn.setStyleSheet(self._tool_button_style())
        if not keep_status:
            QTimer.singleShot(2000, lambda: self.status_label.setText("就绪"))

    def _cleanup_voice_thread(self):
        if hasattr(self, "voice_worker"):
            self.voice_worker.deleteLater()
            self.voice_worker = None
        if hasattr(self, "voice_thread"):
            self.voice_thread.deleteLater()
            self.voice_thread = None

    # ───────────────────────────────
    #  COT 折叠/展开
    # ───────────────────────────────
    #  COT 折叠/展开
    # ───────────────────────────────
    def _on_cot_toggle(self, url):
        """点击 COT 的展开/收起链接"""
        href = url.toString()
        if not href.startswith("#toggle-"):
            return
        toggle_key = href[len("#toggle-"):]
        try:
            idx = int(toggle_key.split("-")[0][3:])
        except ValueError:
            return

        if idx < len(self.messages) and self.messages[idx]["role"] == "cot":
            cot = self.messages[idx]
            if toggle_key in self._cot_expanded:
                self._cot_expanded.discard(toggle_key)
                cot["expanded"] = False
                cot["visible_lines"] = 0
            else:
                self._cot_expanded.add(toggle_key)
                cot["expanded"] = True
                cot["visible_lines"] = 999
        self._lock_scroll_to = idx  # 渲染后定位该消息
        self._render_history()

    # ───────────────────────────────
    #  系统消息
    # ───────────────────────────────
    def _add_system_message(self, text):
        self.messages.append({"role": "system", "text": text})
        self._render_history()

    def _render_history(self):
        """渲染聊天历史"""
        self._do_render()

    def _do_render(self):
        html = """<div style="font-family:Segoe UI,Arial;font-size:14px;line-height:1.6;padding:6px;">"""
        for idx, item in enumerate(self.messages):
            if item["role"] == "cot":
                # 锚点——展开/折叠后定位
                html += f'<a name="msg{idx}"></a>'
                reasoning = item.get("reasoning", "")
                tool_calls = item.get("tool_calls", [])
                visible = item.get("visible_lines", 0)
                expanded = item.get("expanded", False)
                # 历史记录里没有 COT 内容 → 折叠
                if not reasoning and not tool_calls:
                    continue

                if visible > 0 or expanded:
                    # 截取可见行数
                    if not expanded and visible > 0 and reasoning:
                        lines = reasoning.split("\n")
                        shown = "\n".join(lines[:visible])
                        if visible < len(lines):
                            shown += "\n..."
                        reasoning = shown
                    html += build_cot_html(
                        f"cot{idx}", reasoning, tool_calls,
                        self._cot_expanded,
                        streaming=(visible > 0 and not expanded),
                    )
                else:
                    # 折叠状态：只显示摘要行
                    lines_count = reasoning.count("\n") + 1 if reasoning else 0
                    html += f"""
                    <div style="margin:6px 0; display:flex; justify-content:flex-start;">
                        <div style="max-width:85%; background:#111827; border:1px solid #1f2937;
                                    border-radius:14px; padding:6px 14px;">
                            <a href="#toggle-cot{idx}-reasoning"
                               style="color:#fbbf24; font-weight:600; font-size:12px; text-decoration:none;">
                                🤔 思考过程 ▸ 展开 ({lines_count} 行)
                            </a>
                        </div>
                    </div>
                    """
            elif item["role"] == "system":
                text = escape(item['text']).strip()
                html += f"""
                <div style="margin: 6px 0; display:flex; justify-content:center; animation: fadeInUp 0.28s ease;">
                    <div style="background: #1e293b; color: #94a3b8; border-radius: 12px; padding: 6px 14px; font-size: 13px; max-width: 90%; text-align:center; border: 1px solid #334155;">
                        {text}
                    </div>
                </div>
                """
            elif item["role"] == "user":
                text = escape(item['text']).strip()
                text = text.replace('\r\n', '\n').replace('\r', '\n')
                text = text.replace('\n', '<br>')
                html += f"""
                <div style="margin: 6px 0; display:flex; justify-content:flex-end; animation: fadeInUp 0.28s ease;">
                    <div style="max-width: 82%; background: linear-gradient(135deg, #2563eb, #3b82f6); color: #f8fafc; border-radius: 18px 18px 4px 18px; padding: 10px 12px; white-space: normal; box-shadow: 0 6px 16px rgba(37,99,235,0.18);">
                        {text}
                    </div>
                </div>
                """
            else:
                text = escape(item['text']).strip()
                text = text.replace('\r\n', '\n').replace('\r', '\n')
                if item['text'] == "正在思考...":
                    text = "<span style='color:#94a3b8;'>正在思考<span id='loading-dots'>.</span></span>"
                else:
                    text = text.replace('\n', '<br>')
                html += f"""
                <div style="margin: 6px 0; display:flex; justify-content:flex-start; animation: fadeInUp 0.28s ease;">
                    <div style="max-width: 82%; background: #1f2937; color: #e5e7eb; border-radius: 18px 18px 18px 4px; padding: 10px 12px; white-space: normal; box-shadow: 0 6px 16px rgba(0,0,0,0.16);">
                        {text}
                    </div>
                </div>
                """
        html += """
        <style>
            @keyframes fadeInUp { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
            pre { background: #0f172a; color: #e2e8f0; padding: 10px; border-radius: 10px; overflow-x: auto; }
            code { font-family: Consolas, monospace; }
        </style>
        </div>
        """
        # 渲染
        self.history.setHtml(html)

        lock = getattr(self, "_lock_scroll_to", None)
        self._lock_scroll_to = None
        if lock is not None:
            self.history.scrollToAnchor(f"msg{lock}")
        else:
            tc = self.history.textCursor()
            tc.movePosition(tc.MoveOperation.End)
            self.history.setTextCursor(tc)

    def _start_loading(self):
        self.loading_dots = 0
        self.loading_timer = QTimer(self)
        self.loading_timer.timeout.connect(self._animate_loading)
        self.loading_timer.start(450)

    def _animate_loading(self):
        dots = "." * ((self.loading_dots % 3) + 1)
        self.status_label.setText(f"正在思考{dots}")
        self.loading_dots += 1
        self.messages[-1]["text"] = f"正在思考{dots}"
        # 流式时不渲染消息区（由 drip 驱动）
        if not hasattr(self, "_reasoning_drip_active") or not self._reasoning_drip_active:
            self._render_history()

    def _stop_loading(self):
        if hasattr(self, "loading_timer"):
            self.loading_timer.stop()
        self.status_label.setText("就绪")

    def _start_cot_streaming(self, cot_msg: dict, on_done=None):
        """流式展示 COT：逐行出现 → 最后折叠 → 触发 on_done"""
        reasoning = cot_msg.get("reasoning", "")
        total = reasoning.count("\n") + 1 if reasoning else 0
        if total == 0:
            if on_done:
                on_done()
            return

        def _stream():
            current = cot_msg["visible_lines"]
            if current < 4:
                step = 1
            elif current < total:
                step = 2
            else:
                # 全部展示 → 1.5s 后折叠 → 触发答案流式
                QTimer.singleShot(1500, lambda: self._finish_cot(cot_msg, on_done))
                self._cot_timer = None
                return

            cot_msg["visible_lines"] = min(current + step, total)
            self._render_history()

            self._cot_timer = QTimer(self)
            self._cot_timer.setSingleShot(True)
            self._cot_timer.timeout.connect(_stream)
            delay = 120 if cot_msg["visible_lines"] <= 6 else 200
            self._cot_timer.start(delay)

        cot_msg["visible_lines"] = min(3, total)
        self._render_history()
        self._cot_timer = QTimer(self)
        self._cot_timer.setSingleShot(True)
        self._cot_timer.timeout.connect(_stream)
        self._cot_timer.start(250)

    def _finish_cot(self, cot_msg: dict, on_done=None):
        """COT 流式完成：折叠思考链 → 开始答案"""
        if not cot_msg.get("expanded"):
            cot_msg["visible_lines"] = 0
        self._render_history()
        if on_done:
            on_done()

    def _start_streaming(self, text, msg_idx: int | None = None):
        self._stream_text = text
        self._stream_index = 0
        self._stream_msg_idx = msg_idx if msg_idx is not None else len(self.messages) - 1
        self._stream_timer = QTimer(self)
        self._stream_timer.timeout.connect(self._stream_next_char)
        self._stream_timer.start(60)  # 60ms 渲染一次，减少闪烁

    def _stream_next_char(self):
        if self._stream_index < len(self._stream_text):
            idx = self._stream_msg_idx
            chunk = min(3, len(self._stream_text) - self._stream_index)
            self.messages[idx]["text"] += self._stream_text[self._stream_index:self._stream_index + chunk]
            self._stream_index += chunk
            self._render_history()
        else:
            self._stream_timer.stop()
            self._reset_ui()

    def send(self):
        msg = self.input.text().strip()
        if not msg and not self.selected_file:
            return

        display_msg = msg
        if self.selected_file:
            fname = os.path.basename(self.selected_file)
            display_msg = f"{msg}\n📎 附件：{fname}" if msg else f"📎 附件：{fname}"

        self.messages.append({"role": "user", "text": display_msg})
        self.messages.append({"role": "assistant", "text": "正在思考..."})
        self._render_history()
        self.input.clear()
        self.send_btn.setEnabled(False)
        self.input.setEnabled(False)
        self._start_loading()

        file_path = self.selected_file
        self.selected_file = None
        self.file_tag_label.setVisible(False)
        self.cancel_file_btn.setVisible(False)

        if file_path:
            # 附件走旧接口（同步）
            self._send_sync(msg, file_path)
        else:
            # 纯文本走 SSE 流式
            self._send_stream(msg)

    def _send_sync(self, msg, file_path):
        self.thread = QThread(self)
        self.worker = ChatWorker(self.user_id, msg, file_path)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._handle_response)
        self.worker.error.connect(self._handle_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.thread.finished.connect(self._cleanup_thread)
        self.thread.start()

    def _send_stream(self, msg):
        """SSE 流式聊天"""
        self._stream_cot = {
            "role": "cot", "reasoning": "", "tool_calls": [],
            "visible_lines": 0, "expanded": False,
        }
        self._stream_answers = []
        self.messages.insert(len(self.messages) - 1, self._stream_cot)

        self.stop_btn.setVisible(True)
        self.send_btn.setVisible(False)

        self.thread = QThread(self)
        self.worker = StreamChatWorker(self.user_id, msg)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.event_reasoning.connect(self._on_stream_reasoning)
        self.worker.event_answer_chunk.connect(self._on_stream_answer)
        self.worker.event_tool_call.connect(self._on_stream_tool_call)
        self.worker.event_tool_result.connect(self._on_stream_tool_result)
        self.worker.event_command_rewritten.connect(self._on_command_rewritten)
        self.worker.event_done.connect(self._on_stream_done)
        self.worker.event_error.connect(self._on_stream_error)
        self.worker.event_done.connect(self.thread.quit)
        self.worker.event_error.connect(self.thread.quit)
        self.thread.finished.connect(self._cleanup_thread)
        self.thread.start()

    def _stop_streaming(self):
        """打断当前流式输出"""
        self._reasoning_drip_active = False
        self._stop_loading()
        try:
            if hasattr(self, 'thread') and self.thread and self.thread.isRunning():
                self.thread.quit()
                self.thread.wait(500)
        except RuntimeError:
            pass
        # 折叠 COT，显示已有答案
        if hasattr(self, '_stream_cot') and self._stream_cot:
            self._stream_cot["visible_lines"] = 0
        if hasattr(self, '_stream_answers') and self._stream_answers:
            self.messages[-1]["text"] = "".join(self._stream_answers)
        elif self.messages[-1].get("text", "").startswith("正在思考"):
            self.messages[-1]["text"] = "（已中断）"
        self._render_history()
        self._reset_ui()

    def _reset_ui(self):
        self.stop_btn.setVisible(False)
        self.send_btn.setVisible(True)
        self.send_btn.setEnabled(True)
        self.input.setEnabled(True)
        self.status_label.setText("就绪")
        self._save_history()

    def _on_stream_reasoning(self, content: str):
        self._stream_cot["reasoning"] += content
        if not getattr(self, "_reasoning_drip_active", False):
            self._reasoning_drip_active = True
            self._drip_reasoning_lines()
        # 不在此渲染——由 _drip_reasoning_lines 定时驱动

    def _drip_reasoning_lines(self):
        """逐行滴灌思考链，不管后端来多快"""
        total = self._stream_cot["reasoning"].count("\n") + 1
        current = self._stream_cot.get("visible_lines", 0)
        if current >= total:
            self._reasoning_drip_active = False
            return
        self._stream_cot["visible_lines"] = min(current + 1, total)
        self._render_history()
        QTimer.singleShot(800, self._drip_reasoning_lines)

    def _on_stream_answer(self, content: str):
        """缓冲答案，等 COT 完成再显示"""
        self._stream_answers.append(content)

    def _on_stream_tool_call(self, tool: str, command: str):
        self._stream_cot["tool_calls"].append({"tool":tool,"command":command,"result":"执行中..."})
        self._render_history()

    def _on_stream_tool_result(self, tool: str, result: str):
        for tc in self._stream_cot["tool_calls"]:
            if tc["tool"] == tool and tc["result"] == "执行中...":
                tc["result"] = result[:300]; break
        self._render_history()

    def _on_command_rewritten(self, original: str, rewritten: str):
        """问题被重写后，在聊天区显示系统消息"""
        # 截断过长的内容
        orig_short = original[:80] + "..." if len(original) > 80 else original
        rewritten_short = rewritten[:120] + "..." if len(rewritten) > 120 else rewritten
        self._add_system_message(f"🔍 问题已优化：{rewritten_short}")

    def _on_stream_done(self):
        # 等 COT 滴完
        def _wait():
            if getattr(self, "_reasoning_drip_active", False):
                QTimer.singleShot(300, _wait); return
            QTimer.singleShot(1200, self._collapse_and_finish)
        _wait()

    def _collapse_and_finish(self):
        self._stop_loading()
        self._stream_cot["visible_lines"] = 0
        self._render_history()
        answer = "".join(self._stream_answers) if self._stream_answers else ""
        if answer:
            self.messages[-1]["text"] = ""
            self._start_streaming(answer)
        else:
            self.messages[-1]["text"] = "（无回答）"
            self._render_history()
            self._reset_ui()

    def _on_stream_error(self, error_msg: str):
        self._stop_loading()
        self._reasoning_drip_active = False
        self.messages[-1]["text"] = f"错误：{error_msg}"
        self._render_history()
        self._reset_ui()

    def _handle_response(self, result):
        self._stop_loading()

        # 提取内容
        reasoning = ""
        tool_calls = []
        if isinstance(result, dict):
            if "answer" in result:
                answer = result["answer"]
                reasoning = result.get("reasoning", "")
                tool_calls = result.get("tool_calls", [])
            elif "response" in result:
                inner = result["response"]
                if isinstance(inner, dict):
                    answer = inner.get("answer", str(inner))
                    reasoning = inner.get("reasoning", "")
                    tool_calls = inner.get("tool_calls", [])
                else:
                    answer = inner
            else:
                answer = str(result)
        else:
            answer = str(result)

        # 找到助手消息的索引（"正在思考..."那条）
        assistant_idx = len(self.messages) - 1

        if reasoning or tool_calls:
            # 在助手消息前插入 COT，然后流式展示思考链
            cot_msg = {
                "role": "cot",
                "reasoning": reasoning,
                "tool_calls": tool_calls,
                "visible_lines": 0,
                "expanded": False,
            }
            self.messages.insert(assistant_idx, cot_msg)
            # 助手消息索引 +1
            assistant_idx += 1
            # 启动 COT 流式，完成后自动流式输出答案
            QTimer.singleShot(100, lambda: self._start_cot_streaming(
                cot_msg,
                on_done=lambda: self._start_answer(assistant_idx, answer),
            ))
        else:
            # 无 COT，直接流式输出答案
            self._start_answer(assistant_idx, answer)

    def _start_answer(self, assistant_idx: int, answer: str):
        """清除"正在思考..."，开始流式答案"""
        self.messages[assistant_idx]["text"] = ""
        self._render_history()
        self._start_streaming(answer, msg_idx=assistant_idx)

    def _handle_error(self, error_message):
        self._stop_loading()
        self.messages[-1]["text"] = f"错误：{error_message}"
        self._render_history()
        self._reset_ui()

    def _cleanup_thread(self):
        if hasattr(self, "worker"):
            self.worker.deleteLater()
        if hasattr(self, "thread"):
            self.thread.deleteLater()