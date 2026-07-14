from html import escape

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTextEdit,
    QLineEdit,
    QPushButton,
    QLabel,
    QHBoxLayout,
)
from PyQt6.QtCore import Qt, QTimer, QThread, QObject, pyqtSignal

from api import chat


class ChatWorker(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, user_id, message):
        super().__init__()
        self.user_id = user_id
        self.message = message

    def run(self):
        try:
            result = chat(self.user_id, self.message)
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class ChatWindow(QWidget):

    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.setWindowTitle("Kubedoctor")
        self.resize(1080, 780)
        self.setStyleSheet("background: #0f172a; color: #e2e8f0;")
        self.messages = []
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Kubedoctor")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #f8fafc;")
        header.addWidget(title)
        header.addStretch()

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        header.addWidget(self.status_label)
        main_layout.addLayout(header)

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

        composer = QHBoxLayout()
        composer.setContentsMargins(0, 0, 0, 0)
        composer.setSpacing(10)

        self.input = QLineEdit()
        self.input.setPlaceholderText("请输入问题...")
        self.input.setStyleSheet(
            "background: #1f2937; border: 1px solid #374151; border-radius: 999px; padding: 12px 16px; color: #f9fafb;"
        )
        self.input.returnPressed.connect(self.send)

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

        composer.addWidget(self.input, 1)
        composer.addWidget(self.send_btn)
        main_layout.addLayout(composer)

        self.setLayout(main_layout)

    def _render_history(self):
        html = """
        <div style="font-family:Segoe UI, Arial; font-size:14px; line-height:1.6; padding:6px;">
        """
        for item in self.messages:
            if item["role"] == "user":
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
        self._stream_timer.start(28)

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
        if not msg:
            return

        self.messages.append({"role": "user", "text": msg})
        self.messages.append({"role": "assistant", "text": "正在思考..."})
        self._render_history()
        self.input.clear()
        self.send_btn.setEnabled(False)
        self.input.setEnabled(False)
        self._start_loading()

        self.thread = QThread(self)
        self.worker = ChatWorker(self.user_id, msg)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._handle_response)
        self.worker.error.connect(self._handle_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.thread.finished.connect(self._cleanup_thread)
        self.thread.start()

    def _handle_response(self, result):
        self._stop_loading()
        if isinstance(result, dict):
            answer = (
                result.get("response")
                or result.get("answer")
                or result.get("message")
                or str(result)
            )
        else:
            answer = result

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