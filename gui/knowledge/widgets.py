"""
可复用的 GUI 组件

包含: 样式常量、卡片容器、文件拖放区、进度条、状态标签等。
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QProgressBar,
    QPushButton,
    QWidget,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QFont, QDragEnterEvent, QDropEvent


# ══════════════════════════════════════════════════════════
#  样式常量（统一管理，方便主题切换）
# ══════════════════════════════════════════════════════════

class Style:
    BG_DARK = "#0f172a"
    BG_CARD = "#111827"
    BG_INPUT = "#1f2937"
    BG_HOVER = "#374151"
    BORDER = "#334155"
    BORDER_LIGHT = "#374151"
    TEXT_PRIMARY = "#f8fafc"
    TEXT_SECONDARY = "#94a3b8"
    TEXT_BODY = "#e2e8f0"
    ACCENT = "#10b981"
    ACCENT_HOVER = "#059669"
    ACCENT_BLUE = "#3b82f6"
    ACCENT_BLUE_HOVER = "#2563eb"
    DANGER = "#ef4444"
    DANGER_HOVER = "#dc2626"
    WARNING = "#f59e0b"

    # 卡片样式
    CARD = f"""
        QFrame#card {{
            background: {BG_CARD};
            border: 1px solid {BORDER};
            border-radius: 16px;
        }}
    """

    # 主按钮
    BUTTON_PRIMARY = f"""
        QPushButton {{
            background: {ACCENT};
            color: white;
            border: none;
            border-radius: 10px;
            padding: 10px 20px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background: {ACCENT_HOVER};
        }}
        QPushButton:disabled {{
            background: #4b5563;
            color: #9ca3af;
        }}
    """

    # 危险按钮
    BUTTON_DANGER = f"""
        QPushButton {{
            background: {DANGER};
            color: white;
            border: none;
            border-radius: 10px;
            padding: 8px 16px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background: {DANGER_HOVER};
        }}
    """

    # 次要按钮
    BUTTON_SECONDARY = f"""
        QPushButton {{
            background: {BG_INPUT};
            color: {TEXT_PRIMARY};
            border: 1px solid {BORDER_LIGHT};
            border-radius: 10px;
            padding: 10px 20px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background: {BG_HOVER};
        }}
    """

    # 输入框
    INPUT = f"""
        QLineEdit, QTextEdit {{
            background: {BG_INPUT};
            border: 1px solid {BORDER_LIGHT};
            border-radius: 10px;
            padding: 10px 12px;
            color: {TEXT_BODY};
        }}
        QLineEdit:focus, QTextEdit:focus {{
            border-color: {ACCENT};
        }}
    """

    # 标签
    LABEL_HEADER = f"font-size: 20px; font-weight: 700; color: {TEXT_PRIMARY};"
    LABEL_TITLE = f"font-size: 16px; font-weight: 600; color: {TEXT_PRIMARY};"
    LABEL_BODY = f"font-size: 13px; color: {TEXT_SECONDARY};"
    LABEL_ACCENT = f"font-size: 13px; color: {ACCENT}; font-weight: 600;"


# ══════════════════════════════════════════════════════════
#  卡片容器
# ══════════════════════════════════════════════════════════

class Card(QFrame):
    """圆角卡片容器"""

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet(Style.CARD)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        if title:
            header = QLabel(title)
            header.setStyleSheet(Style.LABEL_TITLE)
            layout.addWidget(header)

        self.content_layout = layout

    def add_widget(self, widget: QWidget):
        self.content_layout.addWidget(widget)

    def add_layout(self, layout_):
        self.content_layout.addLayout(layout_)


# ══════════════════════════════════════════════════════════
#  文件拖放区
# ══════════════════════════════════════════════════════════

class DropZone(QFrame):
    """支持拖放的文件选择区域"""

    def __init__(self, accept_multiple: bool = False, parent=None):
        super().__init__(parent)
        self.accept_multiple = accept_multiple
        self._file_paths: list[str] = []
        self.setAcceptDrops(True)
        self.setObjectName("dropZone")
        self.setMinimumHeight(160)
        self.setStyleSheet(
            f"""
            QFrame#dropZone {{
                background: {Style.BG_INPUT};
                border: 2px dashed {Style.BORDER};
                border-radius: 16px;
            }}
            QFrame#dropZone:hover {{
                border-color: {Style.ACCENT};
                background: #1e293b;
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)

        self.icon_label = QLabel("📂")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 36px;")

        self.hint_label = QLabel("拖放文件到此处，或点击下方按钮选择")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setStyleSheet(Style.LABEL_BODY)

        self.count_label = QLabel("")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.count_label.setStyleSheet(Style.LABEL_ACCENT)
        self.count_label.setVisible(False)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.hint_label)
        layout.addWidget(self.count_label)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(
                f"""
                QFrame#dropZone {{
                    background: #1e293b;
                    border: 2px dashed {Style.ACCENT};
                    border-radius: 16px;
                }}
                """
            )

    def dragLeaveEvent(self, event):
        self.setStyleSheet(
            f"""
            QFrame#dropZone {{
                background: {Style.BG_INPUT};
                border: 2px dashed {Style.BORDER};
                border-radius: 16px;
            }}
            """
        )

    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet(
            f"""
            QFrame#dropZone {{
                background: {Style.BG_INPUT};
                border: 2px dashed {Style.BORDER};
                border-radius: 16px;
            }}
            """
        )
        paths = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                paths.append(url.toLocalFile())

        if self.accept_multiple:
            self._file_paths = paths
        else:
            self._file_paths = paths[:1] if paths else []

        self._update_display()

    def set_files(self, paths: list[str]):
        self._file_paths = paths
        self._update_display()

    def get_files(self) -> list[str]:
        return self._file_paths

    def clear(self):
        self._file_paths = []
        self.count_label.setVisible(False)
        self.hint_label.setText("拖放文件到此处，或点击下方按钮选择")
        self.icon_label.setText("📂")

    def _update_display(self):
        count = len(self._file_paths)
        if count == 0:
            self.clear()
            return

        self.count_label.setVisible(True)
        if self.accept_multiple:
            names = "\n".join(
                f"  • {p.split('/')[-1].split('\\\\')[-1]}"
                for p in self._file_paths[:5]
            )
            if count > 5:
                names += f"\n  ... 及其他 {count - 5} 个文件"
            self.hint_label.setText(f"已选择 {count} 个文件：\n{names}")
        else:
            name = self._file_paths[0].split("/")[-1].split("\\")[-1]
            self.hint_label.setText(f"已选择：{name}")

        self.count_label.setText(f"共 {count} 个文件")
        self.icon_label.setText("📄")


# ══════════════════════════════════════════════════════════
#  状态进度条
# ══════════════════════════════════════════════════════════

class StatusBar(QWidget):
    """底部状态栏：进度条 + 状态文字"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # 不确定进度
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(
            f"""
            QProgressBar {{
                background: {Style.BG_INPUT};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background: {Style.ACCENT};
                border-radius: 3px;
            }}
            """
        )

        self.label = QLabel("处理中...")
        self.label.setStyleSheet(Style.LABEL_BODY)

        layout.addWidget(self.label)
        layout.addWidget(self.progress, 1)

    def show_status(self, text: str, indeterminate: bool = True):
        self.label.setText(text)
        self.setVisible(True)
        if indeterminate:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)

    def set_progress(self, value: int):
        self.progress.setRange(0, 100)
        self.progress.setValue(value)

    def hide_status(self):
        self.setVisible(False)


# ══════════════════════════════════════════════════════════
#  空状态占位
# ══════════════════════════════════════════════════════════

class EmptyState(QWidget):
    """列表为空时的占位提示"""

    def __init__(self, icon: str = "📭", message: str = "暂无数据", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)

        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 48px;")

        msg_label = QLabel(message)
        msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg_label.setStyleSheet(Style.LABEL_BODY)

        layout.addWidget(icon_label)
        layout.addWidget(msg_label)
