"""
批量上传页面

功能: 一次性拖入/选择多个文件，批量上传并显示每个文件的结果。
"""

from __future__ import annotations

import os

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QAbstractItemView,
)
from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal

from .widgets import Style, Card, DropZone, StatusBar


class BatchUploadWidget(QWidget):
    """批量上传页面"""

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
        self._clear_results()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # ── Header ──
        self.kb_title = QLabel(f"📂 {self.kb_name}")
        self.kb_title.setStyleSheet(Style.LABEL_HEADER)

        hint = QLabel("一次性拖入或选择多个文档，批量解析并存入知识库")
        hint.setStyleSheet(Style.LABEL_BODY)
        layout.addWidget(self.kb_title)
        layout.addWidget(hint)

        # ── 文件拖放区 ──
        self.drop_zone = DropZone(accept_multiple=True)
        layout.addWidget(self.drop_zone)

        # ── 按钮区 ──
        btn_layout = QHBoxLayout()

        self.select_btn = QPushButton("📁 选择多个文件")
        self.select_btn.setStyleSheet(Style.BUTTON_SECONDARY)
        self.select_btn.clicked.connect(self._select_files)

        self.clear_btn = QPushButton("🗑 清空列表")
        self.clear_btn.setStyleSheet(Style.BUTTON_DANGER)
        self.clear_btn.clicked.connect(self._clear_files)

        self.upload_btn = QPushButton("⬆ 批量上传")
        self.upload_btn.setStyleSheet(Style.BUTTON_PRIMARY)
        self.upload_btn.setEnabled(False)
        self.upload_btn.clicked.connect(self._batch_upload)

        btn_layout.addWidget(self.select_btn)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.upload_btn)
        layout.addLayout(btn_layout)

        # ── 结果表格 ──
        self.result_card = Card("上传结果")
        self.result_card.setVisible(False)

        self.result_table = QTableWidget()
        self.result_table.setColumnCount(3)
        self.result_table.setHorizontalHeaderLabels(["文件名", "状态", "提取数量"])
        self.result_table.horizontalHeader().setStretchLastSection(True)
        self.result_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.result_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.result_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.result_table.setMaximumHeight(300)
        self.result_table.setStyleSheet(
            f"""
            QTableWidget {{
                background: {Style.BG_INPUT};
                border: 1px solid {Style.BORDER};
                border-radius: 8px;
                color: {Style.TEXT_BODY};
                font-size: 13px;
                gridline-color: {Style.BORDER};
            }}
            QHeaderView::section {{
                background: {Style.BG_CARD};
                color: {Style.TEXT_SECONDARY};
                padding: 6px;
                border: none;
                font-weight: 600;
            }}
            QTableWidget::item {{
                padding: 4px 8px;
            }}
            """
        )
        self.result_card.add_widget(self.result_table)
        layout.addWidget(self.result_card)

        # ── 摘要信息 ──
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet(Style.LABEL_ACCENT)
        self.summary_label.setVisible(False)
        layout.addWidget(self.summary_label)

        # ── 状态栏 ──
        self.status_bar = StatusBar()
        layout.addWidget(self.status_bar)

        layout.addStretch()

    def _select_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择文件批量上传",
            "",
            "支持的文档 (*.txt *.md *.log *.docx *.xlsx "
            "*.json *.yaml *.yml *.csv *.xml *.html *.htm "
            "*.py *.sh *.bat *.ps1 *.sql *.cfg *.conf *.ini *.toml);;"
            "所有文件 (*)",
        )
        if files:
            self.drop_zone.set_files(files)
            self.upload_btn.setEnabled(True)

    def _clear_files(self):
        self.drop_zone.clear()
        self.upload_btn.setEnabled(False)

    def _batch_upload(self):
        files = self.drop_zone.get_files()
        if not files:
            QMessageBox.warning(self, "提示", "请先选择要上传的文件")
            return

        # 初始化结果表格
        self.result_card.setVisible(True)
        self.summary_label.setVisible(False)
        self.result_table.setRowCount(len(files))
        for i, fp in enumerate(files):
            name = os.path.basename(fp)
            self.result_table.setItem(i, 0, QTableWidgetItem(name))
            self.result_table.setItem(i, 1, QTableWidgetItem("⏳ 等待..."))
            self.result_table.setItem(i, 2, QTableWidgetItem("-"))
        self.result_table.resizeColumnsToContents()

        self.upload_btn.setEnabled(False)
        self.upload_btn.setText("⏳ 上传中...")
        self.status_bar.show_status("准备上传...")
        self.status_bar.set_progress(0)

        self._upload_index = 0
        self._upload_total = len(files)
        self._upload_files = files
        self._upload_results = []

        # 逐文件上传（非线程）
        self._upload_next()

    def _upload_next(self):
        """上传下一个文件"""
        if self._upload_index >= self._upload_total:
            self._finish_batch()
            return

        fp = self._upload_files[self._upload_index]
        name = os.path.basename(fp)

        # 更新进度
        pct = int(self._upload_index / self._upload_total * 100)
        self.status_bar.set_progress(pct)
        self.status_bar.show_status(
            f"[{self._upload_index + 1}/{self._upload_total}] 正在处理: {name}",
            indeterminate=False,
        )

        # 更新表格行状态
        self.result_table.item(self._upload_index, 1).setText("⏳ 处理中...")
        self.result_table.scrollToItem(
            self.result_table.item(self._upload_index, 0)
        )

        # 启动线程上传单个文件
        self.thread = QThread(self)
        worker = SingleUploadWorker(
            self.kb_id, self.owner, fp,
        )
        worker.moveToThread(self.thread)
        self.thread.started.connect(worker.run)
        worker.finished.connect(lambda r: self._on_file_done(r))
        worker.error.connect(lambda e: self._on_file_error(e))
        worker.finished.connect(self.thread.quit)
        worker.error.connect(self.thread.quit)
        self.thread.finished.connect(self._cleanup_single_thread)
        self.thread.start()

    def _on_file_done(self, result: dict):
        idx = self._upload_index
        name = os.path.basename(self._upload_files[idx])

        if result.get("success"):
            inc_count = result.get("incidents", 0)
            if inc_count > 0:
                self.result_table.item(idx, 1).setText("✅ 成功")
            else:
                self.result_table.item(idx, 1).setText("✅ 已入库(0事件)")
                self.result_table.item(idx, 1).setToolTip(
                    "文档已入库，但未提取到可复用的故障案例"
                )
            self.result_table.item(idx, 2).setText(str(inc_count))
        else:
            err_msg = result.get("message") or result.get("error") or "未知错误"
            self.result_table.item(idx, 1).setText("❌ 失败")
            self.result_table.item(idx, 1).setToolTip(err_msg)
            self.result_table.item(idx, 2).setText("0")

        self._upload_results.append(result)
        self._upload_index += 1
        QApplication.processEvents()

        # 处理下一个
        self._upload_next()

    def _on_file_error(self, error_msg: str):
        idx = self._upload_index
        self.result_table.item(idx, 1).setText("❌ 失败")
        self.result_table.item(idx, 1).setToolTip(str(error_msg))
        self.result_table.item(idx, 2).setText("0")

        self._upload_results.append({
            "success": False,
            "file": self._upload_files[idx],
            "error": error_msg,
        })
        self._upload_index += 1
        QApplication.processEvents()
        self._upload_next()

    def _finish_batch(self):
        self.status_bar.hide_status()
        self.upload_btn.setEnabled(True)
        self.upload_btn.setText("⬆ 批量上传")
        self.summary_label.setVisible(True)
        self.result_table.resizeColumnsToContents()

        success_count = sum(
            1 for r in self._upload_results
            if isinstance(r, dict) and r.get("success")
        )
        total_incidents = sum(
            r.get("incidents", 0)
            for r in self._upload_results
            if isinstance(r, dict)
        )
        fail_count = self._upload_total - success_count

        self.summary_label.setText(
            f"📊 总计 {self._upload_total} 个文件 | "
            f"✅ 成功 {success_count} | "
            f"❌ 失败 {fail_count} | "
            f"📋 提取 {total_incidents} 个 Incident"
        )

        if fail_count > 0:
            QMessageBox.warning(
                self, "批量上传完成",
                f"处理完成：{success_count} 成功，{fail_count} 失败\n"
                f"共提取 {total_incidents} 个 Incident\n\n"
                f"失败原因请鼠标悬停查看表格中 ❌ 行",
            )
        else:
            QMessageBox.information(
                self, "批量上传完成",
                f"全部 {self._upload_total} 个文件上传成功！\n"
                f"共提取 {total_incidents} 个 Incident",
            )

    def _clear_results(self):
        self.result_card.setVisible(False)
        self.summary_label.setVisible(False)
        self.result_table.setRowCount(0)
        self._upload_results = []

    def _cleanup_single_thread(self):
        if hasattr(self, "thread"):
            self.thread.deleteLater()
        if hasattr(self, "worker"):
            self.worker.deleteLater()


class SingleUploadWorker(QObject):
    """上传单个文件的工作线程"""

    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, kb_id: str, owner: str, file_path: str):
        super().__init__()
        self.kb_id = kb_id
        self.owner = owner
        self.file_path = file_path

    def run(self):
        from .knowledge_api import upload_document as single_upload

        try:
            result = single_upload(self.kb_id, self.owner, self.file_path)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
