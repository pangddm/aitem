"""PyMuPDF 坐标级 PDF 提取器 —— 单趟原位插回。

设计：
  1. 用 PyMuPDF 按「块(block)」解析单页，拿到每块的类型、包围盒、文本/图片信息。
  2. 文本与图片走同一通道，按阅读顺序 (y, x) 依次输出：
       - 文本块 → 剔除贯穿型页眉/页脚与页码后，作为 text 原样保留；
       - 图片块 → 按位置/尺寸过滤装饰图，交视觉大模型识别，描述插回原位置。
  3. 页眉/页脚判定：候选区内、且在多个页面重复出现的行判为贯穿型页眉页脚，整份剔除。
  4. 扫描页兜底：某页抽不出任何文本时，整页渲染成 PNG 交视觉/OCR。

可配置（环境变量，见 app/core/config.py）：
  PDF_HEADER_RATIO / PDF_FOOTER_RATIO   页眉页脚区比例
  PDF_MIN_REPEAT                        贯穿重复最少页数
  PDF_MIN_IMAGE_DIM / PDF_MIN_IMAGE_AREA 装饰图过滤阈值
  PDF_IMAGE_RENDER_ZOOM                 图片裁剪渲染兜底的放大倍数
  PDF_OCR_WHOLE_PAGE                    扫描页是否整页走视觉识别
"""

from __future__ import annotations

import os
import re
import uuid
from typing import Any

from app.core.config import (
    PDF_HEADER_RATIO,
    PDF_FOOTER_RATIO,
    PDF_MIN_REPEAT,
    PDF_MIN_IMAGE_DIM,
    PDF_MIN_IMAGE_AREA,
    PDF_IMAGE_RENDER_ZOOM,
    PDF_OCR_WHOLE_PAGE,
    PDF_TABLE_ENABLED,
)

from app.document.limits import check_size, check_pdf_pages

IMAGE_DIR = os.path.join("data", "document_images")

# 页码模式（覆盖中英文常见写法）
_PAGE_NUMBER_RE = re.compile(
    r"^\s*"
    r"(?:"
    r"[Pp]age\s*\d+\s*(?:of\s*\d+)?"
    r"|第\s*\d+\s*页\s*(?:[,，;；]\s*共\s*\d+\s*页)?"
    r"|\d+\s*/\s*\d+"
    r"|-\s*\d+\s*-"
    r"|[-\s]*\d+\s*"
    r")"
    r"\s*$"
)

_WS_RE = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS_RE.sub("", text).lower()


def _is_page_number(text: str) -> bool:
    return bool(_PAGE_NUMBER_RE.match(text.strip()))


def _table_to_markdown(table) -> str:
    """把 PyMuPDF 表格转成 Markdown 表格文本。"""
    try:
        data = table.extract()
    except Exception:
        return ""
    if not data:
        return ""
    rows = [[str(c).replace("\n", " ").strip() if c is not None else "" for c in row] for row in data]
    # 去掉全空行
    rows = [r for r in rows if any(cell for cell in r)]
    if not rows:
        return ""
    max_cols = max(len(r) for r in rows)
    rows = [r + [""] * (max_cols - len(r)) for r in rows]
    lines = []
    lines.append("| " + " | ".join(rows[0]) + " |")
    lines.append("|" + "|".join("---" for _ in rows[0]) + "|")
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)




def _line_zone(y0: float, y1: float, page_h: float) -> str | None:
    if y1 <= PDF_HEADER_RATIO * page_h:
        return "header"
    if y0 >= (1.0 - PDF_FOOTER_RATIO) * page_h:
        return "footer"
    return None


def _page_blocks(page) -> list[dict]:
    """用 dict 模式取单页所有块，已按 (y, x) 排序，并记录页高。"""
    page_h = page.rect.height or 1.0
    out: list[dict] = []
    for blk in page.get_text("dict").get("blocks", []):
        bbox = blk.get("bbox")
        if not bbox:
            continue
        x0, y0, x1, y1 = bbox
        out.append(
            {
                "type": blk.get("type", 0),  # 0=text, 1=image
                "bbox": bbox,
                "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                "v0": y0 / page_h, "v1": y1 / page_h,
                "zone": _line_zone(y0, y1, page_h),
                "lines": blk.get("lines", []),
                "image": blk.get("image"),
                "width": blk.get("width", 0),
                "height": blk.get("height", 0),
                "_page_h": page_h,
            }
        )
    return sorted(out, key=lambda b: (round(b["y0"], 2), b["x0"]))


def _block_text(blk: dict, header_sigs: dict[str, int], footer_sigs: dict[str, int]) -> str:
    page_h = blk["_page_h"]
    kept: list[str] = []
    for ln in blk["lines"]:
        text = "".join(sp.get("text", "") for sp in ln.get("spans", []))
        if not text.strip():
            continue
        y0, y1 = ln["bbox"][1], ln["bbox"][3]
        zone = _line_zone(y0, y1, page_h)
        sig = _norm(text)
        if zone == "header" and sig in header_sigs and header_sigs[sig] >= max(2, PDF_MIN_REPEAT):
            continue
        if zone == "footer" and sig in footer_sigs and footer_sigs[sig] >= max(2, PDF_MIN_REPEAT):
            continue
        if zone in ("header", "footer") and _is_page_number(text):
            continue
        kept.append(text.strip())
    return " ".join(kept)


def _is_decorative_image(blk: dict) -> bool:
    if blk["zone"] in ("header", "footer"):
        return True
    w = blk["x1"] - blk["x0"]
    h = blk["y1"] - blk["y0"]
    if w < 2 or h < 2:
        return True
    pw, ph = blk["width"], blk["height"]
    if pw and ph and min(pw, ph) < PDF_MIN_IMAGE_DIM:
        return True
    if w * h < PDF_MIN_IMAGE_AREA:
        return True
    return False


def _extract_image(doc, page, blk: dict) -> tuple[bytes, str] | None:
    """优先抽原图；失败则渲染该图所在区域兜底，返回 (bytes, ext)。"""
    xref = blk.get("image")
    if xref:
        try:
            info = doc.extract_image(xref)
            return info["image"], info.get("ext", "png")
        except Exception:
            pass
    try:
        import fitz
        rect = fitz.Rect(blk["bbox"])
        mat = fitz.Matrix(PDF_IMAGE_RENDER_ZOOM, PDF_IMAGE_RENDER_ZOOM)
        pix = page.get_pixmap(matrix=mat, clip=rect)
        return pix.tobytes("png"), "png"
    except Exception:
        return None


def _save_image(data: bytes, ext: str) -> str:
    os.makedirs(IMAGE_DIR, exist_ok=True)
    path = os.path.join(IMAGE_DIR, f"pdf_{uuid.uuid4().hex}.{ext}")
    with open(path, "wb") as f:
        f.write(data)
    return path


def _describe_image(image_path: str) -> str:
    from app.llm.vision import analyze_image

    return analyze_image(image_path).strip()


def _extract_items(file_path: str) -> list[dict[str, Any]]:
    """单趟按顺序提取文本与图片，返回按阅读顺序排列的条目。"""
    check_size(file_path)        # 超大文件守卫
    check_pdf_pages(file_path)   # 超大 PDF 守卫
    import fitz

    header_sigs: dict[str, int] = {}
    footer_sigs: dict[str, int] = {}
    pages_blocks: list[list[dict]] = []

    with fitz.open(file_path) as doc:
        # 第一遍：统计贯穿型页眉/页脚的行签名
        for page in doc:
            blocks = _page_blocks(page)
            pages_blocks.append(blocks)
            for blk in blocks:
                if blk["type"] != 0:
                    continue
                for ln in blk["lines"]:
                    y0, y1 = ln["bbox"][1], ln["bbox"][3]
                    zone = _line_zone(y0, y1, blk["_page_h"])
                    if zone not in ("header", "footer"):
                        continue
                    text = "".join(sp.get("text", "") for sp in ln.get("spans", []))
                    sig = _norm(text)
                    if not sig or _is_page_number(text):
                        continue
                    if zone == "header":
                        header_sigs[sig] = header_sigs.get(sig, 0) + 1
                    else:
                        footer_sigs[sig] = footer_sigs.get(sig, 0) + 1

        items: list[dict[str, Any]] = []
        # 第二遍：按阅读顺序输出文本与图片
        for page_no, page in enumerate(doc, start=1):
            blocks = pages_blocks[page_no - 1]
            page_items: list[dict[str, Any]] = []
            page_has_text = False

            for blk in blocks:
                if blk["type"] == 0:
                    text = _block_text(blk, header_sigs, footer_sigs)
                    if text:
                        page_has_text = True
                        page_items.append(
                            {"type": "text", "content": text,
                             "page": page_no, "y0": blk["y0"]}
                        )
                elif blk["type"] == 1:
                    if _is_decorative_image(blk):
                        continue
                    extracted = _extract_image(doc, page, blk)
                    if not extracted:
                        continue
                    data, ext = extracted
                    img_path = _save_image(data, ext)
                    try:
                        desc = _describe_image(img_path)
                    except Exception:
                        desc = ""
                    if not desc:
                        continue
                    page_items.append(
                        {"type": "image", "content": desc,
                         "page": page_no, "y0": blk["y0"]}
                    )


            # PDF 表格 → Markdown（结构化，插回本页对应位置）
            if PDF_TABLE_ENABLED:
                try:
                    for tab in page.find_tables():
                        md = _table_to_markdown(tab)
                        if md:
                            tbbox = tab.bbox
                            page_items.append(
                                {"type": "text", "content": md,
                                 "page": page_no, "y0": tbbox[1], "is_table": True}
                            )
                except Exception:
                    pass


            # 扫描页兜底：整页无文本，且没有任何图片条目 → 整页渲染走视觉
            if not page_has_text and not any(
                i["type"] == "image" for i in page_items
            ) and PDF_OCR_WHOLE_PAGE and any(b["type"] == 1 or b["lines"] for b in blocks):
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img_path = _save_image(pix.tobytes("png"), "png")
                try:
                    desc = _describe_image(img_path)
                except Exception:
                    desc = ""
                if desc:
                    page_items.append(
                        {"type": "image", "content": desc,
                         "page": page_no, "y0": -1.0, "whole_page": True}
                    )

            # 按 y 排序（图片插回原位）
            page_items.sort(key=lambda i: i["y0"])
            items.extend(page_items)

    return items


def extract_pdf_text(file_path: str) -> str:
    """返回全文（图片识别结果原位插入），用于知识库摄入。"""
    parts: list[str] = []
    for it in _extract_items(file_path):
        if it["type"] == "text":
            parts.append(it["content"])
        else:
            parts.append(f"【图片(第{it['page']}页)】{it['content']}")
    return "\n\n".join(parts)


def parse_pdf(file_path: str) -> list[dict]:
    """路由层接口：返回 {type, content, source, metadata}，图片插回原位。"""
    items = _extract_items(file_path)
    return [
        {
            "type": it["type"],
            "content": it["content"],
            "source": file_path,
            "metadata": {
                "file_type": "pdf",
                "page": it["page"],
                "is_image": it["type"] == "image",
                "is_table": it.get("is_table", False),
            },
        }
        for it in items
    ]
