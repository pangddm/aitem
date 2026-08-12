"""文档守卫：超大文件 / 超大 PDF 直接拦截，避免拖垮内存与 API。"""
from __future__ import annotations

import os

from app.core.config import MAX_DOCUMENT_SIZE_MB, MAX_DOCUMENT_PAGES


def check_size(file_path: str) -> int:
    size = os.path.getsize(file_path)
    if MAX_DOCUMENT_SIZE_MB and size > MAX_DOCUMENT_SIZE_MB * 1024 * 1024:
        raise ValueError(
            f"文件超过大小上限 {MAX_DOCUMENT_SIZE_MB:.0f} MB"
        )
    return size


def check_pdf_pages(file_path: str) -> int:
    import fitz

    with fitz.open(file_path) as doc:
        if MAX_DOCUMENT_PAGES and doc.page_count > MAX_DOCUMENT_PAGES:
            raise ValueError(
                f"PDF 页数超过上限 {MAX_DOCUMENT_PAGES} 页"
            )
        return doc.page_count
