"""
单文件上传页面

功能: 选择一个文件上传到指定知识库，显示提取结果。
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QTextEdit,
    QMessageBox,
    QFrame,
)
from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal

from .knowledge_api import upload_document, upload_text
from .widgets import Style, Card, DropZone, StatusBar


class UploadWorker(QObject):
    """后台上传工作线程"""

    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, kb_id: str, owner: str, file_path: str):
        super().__init__()
        self.kb_id = kb_id
        self.owner = owner
        self.file_path = file_path

    def run(self):
        try:
            result = upload_document(self.kb_id, self.owner, self.file_path)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class UploadWidget(QWidget):
    """单文件上传页面"""

    def __init__(self, kb_id: str, kb_name: str, owner: str, parent=None):
        super().__init__(parent)
        self.kb_id = kb_id
        self.kb_name = kb_name
        self.owner = owner

        self.setStyleSheet(f"background: {Style.BG_DARK}; color: {Style.TEXT_BODY};")
        self._setup_ui()

    def refresh(self, kb_id: str, kb_name: str):
        self.kb_id = kb_id
        self.kb_name = kb_name
        self.kb_title.setText(f"📂 {kb_name}")
        self.drop_zone.clear()
        self._clear_result()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # ── Header ──
        self.kb_title = QLabel(f"📂 {self.kb_name}")
        self.kb_title.setStyleSheet(Style.LABEL_HEADER)

        hint = QLabel("选择一个文件，解析后自动提取 Incident 并存入知识库")
        hint.setStyleSheet(Style.LABEL_BODY)

        layout.addWidget(self.kb_title)
        layout.addWidget(hint)

        # ── 文件拖放区 ──
        self.drop_zone = DropZone(accept_multiple=False)
        layout.addWidget(self.drop_zone)

        # ── 选择按钮 ──
        btn_layout = QHBoxLayout()
        self.select_btn = QPushButton("📁 选择文件")
        self.select_btn.setStyleSheet(Style.BUTTON_SECONDARY)
        self.select_btn.clicked.connect(self._select_file)

        self.upload_btn = QPushButton("⬆ 上传并解析")
        self.upload_btn.setStyleSheet(Style.BUTTON_PRIMARY)
        self.upload_btn.setEnabled(False)
        self.upload_btn.clicked.connect(self._upload)

        btn_layout.addWidget(self.select_btn)
        btn_layout.addWidget(self.upload_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # ── 结果卡片 ──
        self.result_card = Card("提取结果")
        self.result_card.setVisible(False)
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMaximumHeight(200)
        self.result_text.setStyleSheet(
            f"""
            QTextEdit {{
                background: {Style.BG_INPUT};
                border: 1px solid {Style.BORDER};
                border-radius: 8px;
                padding: 8px;
                color: {Style.TEXT_BODY};
                font-size: 12px;
                font-family: Consolas, monospace;
            }}
            """
        )
        self.result_card.add_widget(self.result_text)
        layout.addWidget(self.result_card)

        # ── 文本粘贴区 ──
        layout.addSpacing(8)
        text_label = QLabel("或直接粘贴文本：")
        text_label.setStyleSheet(Style.LABEL_TITLE)
        layout.addWidget(text_label)

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("在此粘贴日志、聊天记录、Markdown 笔记...")
        self.text_input.setMaximumHeight(120)
        self.text_input.setStyleSheet(Style.INPUT)
        layout.addWidget(self.text_input)

        text_upload_btn = QPushButton("📝 提交文本")
        text_upload_btn.setStyleSheet(Style.BUTTON_SECONDARY)
        text_upload_btn.clicked.connect(self._upload_text)
        layout.addWidget(text_upload_btn)

        # ── 状态栏 ──
        self.status_bar = StatusBar()
        layout.addWidget(self.status_bar)

        layout.addStretch()

    def _select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文件上传到知识库",
            "",
            "支持的文档 (*.txt *.md *.log *.docx *.xlsx "
            "*.json *.yaml *.yml *.csv *.xml *.html *.htm "
            "*.py *.sh *.bat *.ps1 *.sql *.cfg *.conf *.ini *.toml);;"
            "所有文件 (*)",
        )
        if file_path:
            self.drop_zone.set_files([file_path])
            self.upload_btn.setEnabled(True)

    def _upload(self):
        files = self.drop_zone.get_files()
        if not files:
            QMessageBox.warning(self, "提示", "请先选择文件")
            return

        self.upload_btn.setEnabled(False)
        self.upload_btn.setText("⏳ 上传中...")
        self.status_bar.show_status("正在上传并解析文档...")

        self.thread = QThread(self)
        self.worker = UploadWorker(self.kb_id, self.owner, files[0])
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_upload_done)
        self.worker.error.connect(self._on_upload_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.thread.finished.connect(self._cleanup_thread)
        self.thread.start()

    def _on_upload_done(self, result: dict):
        self.status_bar.hide_status()
        self.upload_btn.setEnabled(True)
        self.upload_btn.setText("⬆ 上传并解析")

        if result.get("success"):
            count = result.get("incidents", 0)
            self.result_card.setVisible(True)

            if count > 0:
                incidents = result.get("data", [])
                lines = [f"✅ 成功提取 {count} 个 Incident：\n"]
                for i, inc in enumerate(incidents, 1):
                    lines.append(
                        f"  {i}. {inc.get('title', '无标题')}\n"
                        f"     摘要: {inc.get('summary', '')[:80]}...\n"
                    )
                self.result_text.setText("".join(lines))
            else:
                self.result_text.setText(
                    "⚠️ 文档已上传，但未提取到可复用的 Incident。\n"
                    "文档内容可能不包含排障信息。"
                )
            QMessageBox.information(
                self, "完成", f"文档上传成功，提取了 {count} 个 Incident"
            )
        else:
            QMessageBox.warning(
                self, "失败", result.get("message", "上传失败")
            )

    def _on_upload_error(self, error_msg: str):
        self.status_bar.hide_status()
        self.upload_btn.setEnabled(True)
        self.upload_btn.setText("⬆ 上传并解析")
        QMessageBox.critical(self, "错误", error_msg)

    def _upload_text(self):
        text = self.text_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请先输入文本内容")
            return

        filename = f"paste_{self.kb_id[:8]}.txt"
        self.status_bar.show_status("正在提交文本...")

        try:
            result = upload_text(self.kb_id, self.owner, filename, text)
            if result.get("success"):
                count = result.get("incidents", 0)
                self.result_card.setVisible(True)
                self.result_text.setText(
                    f"✅ 文本提交成功，提取了 {count} 个 Incident"
                )
                self.text_input.clear()
                QMessageBox.information(
                    self, "完成", f"文本提交成功，提取了 {count} 个 Incident"
                )
            else:
                QMessageBox.warning(
                    self, "失败", result.get("message", "提交失败")
                )
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))
        finally:
            self.status_bar.hide_status()

    def _clear_result(self):
        self.result_card.setVisible(False)
        self.result_text.clear()

    def _cleanup_thread(self):
        if hasattr(self, "worker"):
            self.worker.deleteLater()
        if hasattr(self, "thread"):
            self.thread.deleteLater()
