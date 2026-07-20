from __future__ import annotations

import re
from dataclasses import dataclass

# 标题模式：Markdown #, 中文"第X章", 编号 1./1.1., 【标题】, 分隔线
_HEADER_RE = re.compile(
    r"(?:^|\n)(?:#{1,6}\s|第[一二三四五六七八九十\d]+[章节]\s)"
    r"|(?:^|\n)(?:\d+\.)+\s"       # 1. / 1.1. 编号
    r"|(?:^|\n)【[^】]+】"          # 【标题】
    r"|(?:^|\n)(?:[A-Z][A-Za-z ]+)\n[-=]+\n"  # 英文 underline 标题
    r"|(?:^|\n)-{3,}\s*\n",        # --- 分隔线
    re.MULTILINE,
)


@dataclass
class TextChunk:
    """文本分片 — 保持语义完整"""

    text: str
    index: int


class TextSplitter:

    def split(
        self,
        text: str,
        chunk_size: int = 30000,
    ) -> list[TextChunk]:

        if len(text) <= chunk_size:
            return [TextChunk(text=text, index=0)]

        # 策略 1: 按章节/标题切
        sections = self._split_by_headers(text)
        if len(sections) > 1 and self._any_in_limit(sections, chunk_size):
            return self._merge_small(sections, chunk_size)

        # 策略 2: 按段落切
        paragraphs = [
            p.strip() for p in
            re.split(r"\n{2,}", text.strip())
            if len(p.strip()) > 20
        ]
        if len(paragraphs) > 1:
            return self._merge_small(paragraphs, chunk_size)

        # 策略 3: 字符切（在换行处对齐）
        return self._split_by_char(text, chunk_size)

    # ────────── 分割 ────────────────────────────────────

    @staticmethod
    def _split_by_headers(text: str) -> list[str]:
        matches = list(_HEADER_RE.finditer(text))
        if not matches:
            return [text]

        parts = []
        prev = 0
        for m in matches:
            if m.start() > prev:
                parts.append(text[prev: m.start()].strip())
            prev = m.start()
        if prev < len(text):
            parts.append(text[prev:].strip())

        return [p for p in parts if len(p) > 50]

    @staticmethod
    def _split_by_char(text: str, size: int) -> list[TextChunk]:
        chunks = []
        start = 0
        idx = 0
        while start < len(text):
            end = start + size
            if end < len(text):
                br = text.rfind("\n", start, end)
                if br > start + size // 2:
                    end = br + 1
            chunks.append(
                TextChunk(text=text[start:end].strip(), index=idx)
            )
            start = end
            idx += 1
        return chunks

    # ────────── 合并 ────────────────────────────────────

    def _merge_small(
        self,
        parts: list[str],
        target: int,
    ) -> list[TextChunk]:
        chunks = []
        buf = ""
        idx = 0

        for part in parts:
            if not part.strip():
                continue

            # 标题行有时太短，单独保留
            is_header = _HEADER_RE.match(part) and len(part) < 200

            if len(buf) + len(part) <= target or is_header:
                if buf and not is_header:
                    buf += "\n\n" + part
                elif is_header and buf.strip():
                    chunks.append(TextChunk(text=buf.strip(), index=idx))
                    idx += 1
                    chunks.append(TextChunk(text=part, index=idx))
                    idx += 1
                    buf = ""
                    continue
                else:
                    buf = part
            else:
                if buf.strip():
                    chunks.append(TextChunk(text=buf.strip(), index=idx))
                    idx += 1
                buf = part

        if buf.strip():
            chunks.append(TextChunk(text=buf.strip(), index=idx))

        return chunks or [TextChunk(text="\n\n".join(parts), index=0)]

    @staticmethod
    def _any_in_limit(parts: list[str], limit: int) -> bool:
        return any(len(p) <= limit for p in parts if p.strip())