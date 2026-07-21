import os
from html import escape

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTextEdit,
    QLineEdit,
    QPushButton,
    QLabel,
    QHBoxLayout,
    QFileDialog,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer, QThread

from api import chat, chat_with_document
from knowledge.kb_window import KnowledgeWindow
from chat.workers import ChatWorker, VoiceWorker
from chat.cot_html import build_cot_html


class ChatWindow(QWidget):

    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.setWindowTitle("Kubedoctor")
        self.resize(1080, 780)
        self.setStyleSheet("background: #0f172a; color: #e2e8f0;")
        self.messages = []
        self.is_recording = False
        self.selected_file = None  # 当前待发送的附件路径
        self.init_ui()

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

        header.addStretch()

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        header.addWidget(self.status_label)
        main_layout.addLayout(header)

        # ── Chat History ──
        self.history = QTextEdit()
        self.history.setReadOnly(True)
        self.history.setAcceptRichText(True)
        self.history.setStyleSheet(
            "background: #111827; border: 1px solid #1f2937; border-radius: 16px; padding: 10px; color: #f8fafc;"
        )
        self.history.setPlaceholderText("开始你的问题吧...")
        self.history.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.history.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
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

        composer.addWidget(self.attach_btn)
        composer.addWidget(self.voice_btn)
        composer.addWidget(self.input, 1)
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
    #  系统消息
    # ───────────────────────────────
    def _add_system_message(self, text):
        self.messages.append({"role": "system", "text": text})
        self._render_history()

    def _render_history(self):
        html = """
        <div style="font-family:Segoe UI, Arial; font-size:14px; line-height:1.6; padding:6px;">
        """
        for item in self.messages:
            if item["role"] == "cot":
                html += item["html"]
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
                if item['text'] == "正在生成...":
                    text = "<span style='color:#94a3b8;'>正在生成<span id='loading-dots'>.</span></span>"
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
        self.history.setHtml(html)
        cursor = self.history.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.history.setTextCursor(cursor)
        self.history.ensureCursorVisible()
        scrollbar = self.history.verticalScrollBar()
        if scrollbar is not None:
            scrollbar.setValue(scrollbar.maximum())

    def _start_loading(self):
        self.loading_dots = 0
        self.loading_timer = QTimer(self)
        self.loading_timer.timeout.connect(self._animate_loading)
        self.loading_timer.start(450)

    def _animate_loading(self):
        dots = "." * ((self.loading_dots % 3) + 1)
        self.status_label.setText(f"正在思考{dots}")
        self.loading_dots += 1
        self.messages[-1]["text"] = "正在生成..."
        self._render_history()

    def _stop_loading(self):
        if hasattr(self, "loading_timer"):
            self.loading_timer.stop()
        self.status_label.setText("就绪")

    def _start_streaming(self, text):
        self._stream_text = text
        self._stream_index = 0
        self._stream_timer = QTimer(self)
        self._stream_timer.timeout.connect(self._stream_next_char)
        self._stream_timer.start(15)

    def _stream_next_char(self):
        if self._stream_index < len(self._stream_text):
            self.messages[-1]["text"] += self._stream_text[self._stream_index]
            self._stream_index += 1
            self._render_history()
        else:
            self._stream_timer.stop()
            self.send_btn.setEnabled(True)
            self.input.setEnabled(True)
            self.status_label.setText("就绪")

    def send(self):
        msg = self.input.text().strip()
        if not msg and not self.selected_file:
            return

        # 显示用户消息（含附件信息）
        display_msg = msg
        file_info = ""
        if self.selected_file:
            fname = os.path.basename(self.selected_file)
            file_info = f" [📎 {fname}]"
            display_msg = f"{msg}\n📎 附件：{fname}" if msg else f"📎 附件：{fname}"

        self.messages.append({"role": "user", "text": display_msg})
        self.messages.append({"role": "assistant", "text": "正在思考..."})
        self._render_history()
        self.input.clear()
        self.send_btn.setEnabled(False)
        self.input.setEnabled(False)
        self._start_loading()

        self.thread = QThread(self)
        self.worker = ChatWorker(self.user_id, msg, self.selected_file)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._handle_response)
        self.worker.error.connect(self._handle_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.thread.finished.connect(self._cleanup_thread)
        self.thread.start()

        # 清除附件标记
        self.selected_file = None
        self.file_tag_label.setVisible(False)
        self.cancel_file_btn.setVisible(False)

    def _handle_response(self, result):
        self._stop_loading()

        # 提取内容（兼容多种返回格式）
        reasoning = ""
        tool_calls = []
        if isinstance(result, dict):
            # /chat 直接返回 {"answer":..., "reasoning":..., "tool_calls":...}
            if "answer" in result:
                answer = result["answer"]
                reasoning = result.get("reasoning", "")
                tool_calls = result.get("tool_calls", [])
            # /chat_with_document 返回 {"response": {...}}
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

        # 先渲染 COT（思考链 + 工具调用）
        cot_html = build_cot_html(reasoning, tool_calls)
        if cot_html:
            self.messages.append({"role": "cot", "html": cot_html})

        # 后渲染最终回答
        self.messages[-1]["text"] = ""
        self._render_history()
        self._start_streaming(answer)

    def _handle_error(self, error_message):
        self._stop_loading()
        self.messages[-1]["text"] = f"错误：{error_message}"
        self._render_history()
        self.send_btn.setEnabled(True)
        self.input.setEnabled(True)

    def _cleanup_thread(self):
        if hasattr(self, "worker"):
            self.worker.deleteLater()
        if hasattr(self, "thread"):
            self.thread.deleteLater()