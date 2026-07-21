"""
知识库管理主窗口

页面索引:
  0 - 知识库列表
  1 - 上传方式选择（预创建，不复建）
  2 - 单文件上传
  3 - 批量上传
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame,
)
from PyQt6.QtCore import Qt

from .kb_list_widget import KbListWidget
from .upload_widget import UploadWidget
from .batch_upload_widget import BatchUploadWidget
from .widgets import Style

PAGE_LIST = 0
PAGE_CHOICE = 1
PAGE_UPLOAD = 2
PAGE_BATCH = 3


class KnowledgeWindow(QWidget):

    def __init__(self, owner: str, parent=None):
        super().__init__(parent)
        self.owner = owner
        self._current_kb_id: str | None = None
        self._current_kb_name: str = ""

        self.setWindowTitle("知识库管理 - Kubedoctor")
        self.resize(1100, 720)
        self.setStyleSheet(f"background: {Style.BG_DARK}; color: {Style.TEXT_BODY};")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 导航栏 ──
        nav_bar = QFrame()
        nav_bar.setObjectName("nav")
        nav_bar.setFixedHeight(52)
        nav_bar.setStyleSheet(f"""
            QFrame#nav {{
                background: {Style.BG_CARD};
                border-bottom: 1px solid {Style.BORDER};
            }}
        """)
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(16, 0, 16, 0)

        self.nav_title = QLabel("📚 知识库管理")
        self.nav_title.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {Style.TEXT_PRIMARY};"
        )
        self.breadcrumb = QLabel("")
        self.breadcrumb.setStyleSheet(
            f"font-size: 13px; color: {Style.TEXT_SECONDARY}; padding-left: 12px;"
        )
        nav_layout.addWidget(self.nav_title)
        nav_layout.addWidget(self.breadcrumb)
        nav_layout.addStretch()

        self.back_btn = QPushButton("← 返回列表")
        self.back_btn.setStyleSheet(Style.BUTTON_SECONDARY)
        self.back_btn.setVisible(False)
        self.back_btn.clicked.connect(self._go_back_to_list)
        nav_layout.addWidget(self.back_btn)

        layout.addWidget(nav_bar)

        # ── 4 个页面预创建，固定索引 ──
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background: {Style.BG_DARK};")

        self.kb_list_page = KbListWidget(self.owner)               # 0
        self.kb_list_page.enter_kb.connect(self._on_enter_kb)
        self.choice_page = self._build_choice_page()                # 1
        self.upload_page = UploadWidget("", "", self.owner)        # 2
        self.batch_page = BatchUploadWidget("", "", self.owner)    # 3

        for p in (self.kb_list_page, self.choice_page,
                  self.upload_page, self.batch_page):
            self.stack.addWidget(p)

        self.stack.setCurrentIndex(PAGE_LIST)
        layout.addWidget(self.stack, 1)

        # 事件过滤器：让拖放事件穿透 QStackedWidget 到达批量上传页
        self.stack.installEventFilter(self)

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj is self.stack and self.stack.currentIndex() == PAGE_BATCH:
            t = event.type()
            if t in (QEvent.Type.DragEnter, QEvent.Type.DragMove, QEvent.Type.Drop):
                self.batch_page.event(event)
                return True
        return super().eventFilter(obj, event)

    # ── 选择页 ──────────────────────────────────────────

    def _build_choice_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background: {Style.BG_DARK};")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        self.choice_title = QLabel("")
        self.choice_title.setStyleSheet(Style.LABEL_HEADER)
        self.choice_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.choice_title)

        desc = QLabel("选择一种方式向知识库中添加文档")
        desc.setStyleSheet(Style.LABEL_BODY)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)
        layout.addSpacing(20)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(24)
        btn_layout.addWidget(self._choice_card(
            "📄", "单文件上传", "选择一个文件上传，查看详细提取结果",
            "选择文件 → 解析 → 查看 Incident",
            lambda: self._jump_to(PAGE_UPLOAD, "上传"),
        ))
        btn_layout.addWidget(self._choice_card(
            "📦", "批量上传", "一次拖入或选择多个文件，批量处理",
            "拖入文件 → 批量解析 → 查看汇总",
            lambda: self._jump_to(PAGE_BATCH, "批量"),
        ))
        layout.addLayout(btn_layout)
        layout.addStretch()
        return page

    @staticmethod
    def _choice_card(icon: str, title: str, desc: str,
                     hint: str, on_click) -> QFrame:
        card = QFrame()
        card.setObjectName("choiceCard")
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setStyleSheet(f"""
            QFrame#choiceCard {{
                background: {Style.BG_CARD};
                border: 2px solid {Style.BORDER};
                border-radius: 20px;
                padding: 24px;
            }}
            QFrame#choiceCard:hover {{
                border-color: {Style.ACCENT};
                background: #1e293b;
            }}
        """)
        card.setMinimumSize(280, 200)
        card._cb = on_click
        card.mousePressEvent = lambda e: card._cb()

        cl = QVBoxLayout(card)
        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.setSpacing(12)
        for txt, sty in [
            (icon, "font-size: 48px;"),
            (title, f"font-size: 18px; font-weight: 700; color: {Style.TEXT_PRIMARY};"),
            (desc, Style.LABEL_BODY),
            (hint, Style.LABEL_ACCENT),
        ]:
            lbl = QLabel(txt)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(sty)
            cl.addWidget(lbl)
        return card

    # ── 导航 ────────────────────────────────────────────

    def _jump_to(self, idx: int, name: str):
        self.breadcrumb.setText(f"› {self._current_kb_name} › {name}")
        self.stack.setCurrentIndex(idx)

    def _on_enter_kb(self, kb_id: str, kb_name: str):
        self._current_kb_id = kb_id
        self._current_kb_name = kb_name
        self.upload_page.refresh(kb_id, kb_name)
        self.batch_page.refresh(kb_id, kb_name)
        self.choice_title.setText(f"📖 {kb_name}")
        self.breadcrumb.setText(f"› {kb_name}")
        self.back_btn.setVisible(True)
        self.nav_title.setText(f"📖 {kb_name}")
        self.stack.setCurrentIndex(PAGE_CHOICE)

    def _go_back_to_list(self):
        self._current_kb_id = None
        self._current_kb_name = ""
        self.breadcrumb.setText("")
        self.back_btn.setVisible(False)
        self.nav_title.setText("📚 知识库管理")
        self.stack.setCurrentIndex(PAGE_LIST)
        self.kb_list_page._load_kbs()
