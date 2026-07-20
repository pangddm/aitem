"""
知识库列表页面

功能: 创建、查看、刷新、删除知识库，选择后进入上传/管理。
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QListWidget,
    QListWidgetItem,
    QDialog,
    QMessageBox,
    QSplitter,
    QFrame,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication

from .knowledge_api import create_kb, list_kbs, delete_kb, get_kb_stats
from .widgets import Style, Card, EmptyState


class CreateKbDialog(QDialog):
    """创建知识库对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("创建知识库")
        self.resize(420, 320)
        self.setStyleSheet(f"background: {Style.BG_DARK}; color: {Style.TEXT_BODY};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("创建新知识库")
        title.setStyleSheet(Style.LABEL_HEADER)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("知识库名称（必填）")
        self.name_input.setStyleSheet(Style.INPUT)

        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("描述（可选）")
        self.desc_input.setMaximumHeight(80)
        self.desc_input.setStyleSheet(Style.INPUT)

        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet(Style.BUTTON_SECONDARY)
        cancel_btn.clicked.connect(self.reject)

        self.confirm_btn = QPushButton("创建")
        self.confirm_btn.setStyleSheet(Style.BUTTON_PRIMARY)
        self.confirm_btn.clicked.connect(self._create)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self.confirm_btn)

        layout.addWidget(title)
        layout.addWidget(self.name_input)
        layout.addWidget(self.desc_input)
        layout.addStretch()
        layout.addLayout(btn_layout)

    def _create(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入知识库名称")
            return
        self.kb_name = name
        self.kb_description = self.desc_input.toPlainText().strip()
        self.accept()


class KbListWidget(QWidget):
    """知识库列表页面"""

    # 选择知识库后触发的信号，供父窗口连接
    enter_kb = pyqtSignal(str, str)  # kb_id, kb_name

    def __init__(self, owner: str, parent=None):
        super().__init__(parent)
        self.owner = owner
        self._kbs: list[dict] = []
        self._selected_kb_id: str | None = None

        self.setStyleSheet(f"background: {Style.BG_DARK}; color: {Style.TEXT_BODY};")
        self._setup_ui()
        self._load_kbs()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # ── Header ──
        header = QHBoxLayout()
        title = QLabel("我的知识库")
        title.setStyleSheet(Style.LABEL_HEADER)

        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.setStyleSheet(Style.BUTTON_SECONDARY)
        self.refresh_btn.clicked.connect(self._load_kbs)

        self.create_btn = QPushButton("＋ 新建知识库")
        self.create_btn.setStyleSheet(Style.BUTTON_PRIMARY)
        self.create_btn.clicked.connect(self._create_kb)

        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.refresh_btn)
        header.addWidget(self.create_btn)
        layout.addLayout(header)

        # ── 分割: 左列表 + 右详情 ──
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧列表
        left_panel = QFrame()
        left_panel.setObjectName("card")
        left_panel.setStyleSheet(
            f"""
            QFrame#card {{
                background: {Style.BG_CARD};
                border: 1px solid {Style.BORDER};
                border-radius: 12px;
            }}
            """
        )
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)

        self.kb_list = QListWidget()
        self.kb_list.setStyleSheet(
            f"""
            QListWidget {{
                background: transparent;
                border: none;
                color: {Style.TEXT_BODY};
                font-size: 14px;
            }}
            QListWidget::item {{
                padding: 10px 12px;
                border-radius: 8px;
                margin: 2px 0px;
            }}
            QListWidget::item:hover {{
                background: {Style.BG_HOVER};
            }}
            QListWidget::item:selected {{
                background: {Style.ACCENT};
                color: white;
            }}
            """
        )
        self.kb_list.currentRowChanged.connect(self._on_select_kb)
        left_layout.addWidget(self.kb_list)

        # 右侧详情
        right_panel = QFrame()
        right_panel.setObjectName("card")
        right_panel.setStyleSheet(
            f"""
            QFrame#card {{
                background: {Style.BG_CARD};
                border: 1px solid {Style.BORDER};
                border-radius: 12px;
            }}
            """
        )
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)

        self.detail_widget = QWidget()
        self.detail_widget.setStyleSheet("background: transparent;")
        detail_layout = QVBoxLayout(self.detail_widget)
        detail_layout.setSpacing(8)

        self.detail_title = QLabel("选择一个知识库")
        self.detail_title.setStyleSheet(Style.LABEL_TITLE)

        self.detail_desc = QLabel("")
        self.detail_desc.setStyleSheet(Style.LABEL_BODY)
        self.detail_desc.setWordWrap(True)

        self.detail_stats = QLabel("")
        self.detail_stats.setStyleSheet(Style.LABEL_BODY)

        self.detail_id = QLabel("")
        self.detail_id.setStyleSheet(Style.LABEL_BODY)
        self.detail_id.setWordWrap(True)

        detail_layout.addWidget(self.detail_title)
        detail_layout.addWidget(self.detail_desc)
        detail_layout.addWidget(self.detail_stats)
        detail_layout.addWidget(self.detail_id)
        detail_layout.addStretch()

        # 操作按钮
        action_layout = QHBoxLayout()
        self.enter_btn = QPushButton("📂 进入管理")
        self.enter_btn.setStyleSheet(Style.BUTTON_PRIMARY)
        self.enter_btn.setVisible(False)
        self.enter_btn.clicked.connect(self._on_enter_kb)

        self.delete_btn = QPushButton("🗑 删除")
        self.delete_btn.setStyleSheet(Style.BUTTON_DANGER)
        self.delete_btn.setVisible(False)
        self.delete_btn.clicked.connect(self._on_delete_kb)

        action_layout.addWidget(self.enter_btn)
        action_layout.addStretch()
        action_layout.addWidget(self.delete_btn)

        self.detail_empty = EmptyState("📚", "请选择或创建一个知识库")

        right_layout.addWidget(self.detail_widget)
        right_layout.addWidget(self.detail_empty)
        right_layout.addLayout(action_layout)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([280, 500])
        layout.addWidget(splitter, 1)

    def _load_kbs(self):
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("⏳ 加载中...")
        QApplication.processEvents()

        try:
            result = list_kbs(self.owner)
            if result.get("success"):
                self._kbs = result.get("data", [])
            else:
                self._kbs = []
        except Exception:
            self._kbs = []

        self.kb_list.blockSignals(True)
        self.kb_list.clear()
        for kb in self._kbs:
            item = QListWidgetItem(f"  📖 {kb.get('name', '未命名')}")
            item.setData(Qt.ItemDataRole.UserRole, kb.get("id"))
            self.kb_list.addItem(item)

        self.kb_list.blockSignals(False)
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("🔄 刷新")

        if self._kbs:
            self.kb_list.setCurrentRow(0)
        else:
            self._show_empty_detail()

        self.kb_list.repaint()

    def _on_select_kb(self, row: int):
        if row < 0 or row >= len(self._kbs):
            return
        kb = self._kbs[row]
        self._selected_kb_id = kb.get("id")
        self._show_kb_detail(kb)

    def _show_kb_detail(self, kb: dict):
        self.detail_widget.setVisible(True)
        self.detail_empty.setVisible(False)
        self.enter_btn.setVisible(True)
        self.delete_btn.setVisible(True)

        self.detail_title.setText(f"📖 {kb.get('name', '未命名')}")
        desc = kb.get("description") or "暂无描述"
        self.detail_desc.setText(f"描述：{desc}")
        self.detail_id.setText(f"ID：{kb.get('id', '')}")

        # 异步加载统计
        QTimer.singleShot(100, lambda: self._load_stats(kb.get("id", "")))

    def _load_stats(self, kb_id: str):
        try:
            stats = get_kb_stats(kb_id)
            if stats.get("success"):
                self.detail_stats.setText(
                    f"📄 文档：{stats.get('document_count', 0)} 个  "
                    f"📋 案例：{stats.get('incident_count', 0)} 个"
                )
        except Exception:
            self.detail_stats.setText("统计信息加载失败")

    def _show_empty_detail(self):
        self.detail_widget.setVisible(False)
        self.detail_empty.setVisible(True)
        self.enter_btn.setVisible(False)
        self.delete_btn.setVisible(False)

    def _create_kb(self):
        dialog = CreateKbDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                result = create_kb(
                    owner=self.owner,
                    name=dialog.kb_name,
                    description=dialog.kb_description,
                )
                if result.get("success"):
                    QMessageBox.information(self, "成功", "知识库创建成功")
                    self._load_kbs()
                else:
                    QMessageBox.warning(
                        self, "失败", result.get("message", "创建失败")
                    )
            except Exception as e:
                QMessageBox.critical(self, "错误", str(e))

    def _on_delete_kb(self):
        if not self._selected_kb_id:
            return
        reply = QMessageBox.question(
            self,
            "确认删除",
            "确定要删除此知识库吗？\n所有文档和案例将被级联删除，不可恢复！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            result = delete_kb(self._selected_kb_id)
            if result.get("success"):
                QMessageBox.information(self, "成功", "知识库已删除")
                self._load_kbs()
            else:
                QMessageBox.warning(self, "失败", result.get("message", "删除失败"))
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))

    def _on_enter_kb(self):
        """进入知识库管理页面 — 通过信号解耦"""
        if self._selected_kb_id:
            kb_name = ""
            for kb in self._kbs:
                if kb.get("id") == self._selected_kb_id:
                    kb_name = kb.get("name", "")
                    break
            self.enter_kb.emit(self._selected_kb_id, kb_name)

    def current_kb_id(self) -> str | None:
        return self._selected_kb_id
