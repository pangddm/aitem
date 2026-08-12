from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Optional

from app.core.config import CHUNK_SIZE, CHUNK_OVERLAP

# 标题模式：Markdown #, 中文"第X章", 编号 1./1.1., 【标题】, 分隔线
_HEADER_RE = re.compile(
    r"(?:^|\n)(?:#{1,6}\s|第[一二三四五六七八九十\d]+[章节]\s)"
    r"|(?:^|\n)(?:\d+\.)+\s"       # 1. / 1.1. 编号
    r"|(?:^|\n)【[^】]+】"          # 【标题】
    r"|(?:^|\n)(?:[A-Z][A-Za-z ]+)\n[-=]+\n"  # 英文 underline 标题
    r"|(?:^|\n)-{3,}\s*\n",        # --- 分隔线
    re.MULTILINE,
)


def _approx_tokens(text: str) -> int:
    """粗略估算 token 数：中文/英文混排按 ~1.6 字符/token 估算。"""
    if not text:
        return 0
    return max(1, int(math.ceil(len(text) / 1.6)))


@dataclass
class TextChunk:
    """文本分片 — 保持语义完整"""

    text: str
    index: int
    token_estimate: int = 0


class TextSplitter:

    def split(
        self,
        text: str,
        chunk_size: int | None = None,
        overlap: int | None = None,
    ) -> list[TextChunk]:

        size = chunk_size or (CHUNK_SIZE or 30000)
        olap = CHUNK_OVERLAP if overlap is None else overlap
        if olap and olap >= size:
            olap = max(0, size // 10)

        if len(text) <= size:
            return [TextChunk(text=text, index=0, token_estimate=_approx_tokens(text))]

        # 策略 1: 按章节/标题切
        sections = self._split_by_headers(text)
        if len(sections) > 1 and self._any_in_limit(sections, size):
            return self._merge_small(sections, size)

        # 策略 2: 按段落切
        paragraphs = [
            p.strip() for p in
            re.split(r"\n{2,}", text.strip())
            if len(p.strip()) > 20
        ]
        if len(paragraphs) > 1:
            return self._merge_small(paragraphs, size)

        # 策略 3: 字符切（在换行处对齐），并带 overlap
        return self._split_by_char(text, size, olap)

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

    @classmethod
    def _split_by_char(
        cls,
        text: str,
        size: int,
        overlap: int = 0,
    ) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        n = len(text)
        start = 0
        idx = 0
        while start < n:
            end = start + size
            if end < n:
                br = text.rfind("\n", start, end)
                if br > start + size // 2:
                    end = br + 1
            content = text[start:end].strip()
            if content:
                chunks.append(
                    TextChunk(
                        text=content,
                        index=idx,
                        token_estimate=_approx_tokens(content),
                    )
                )
                idx += 1

            if end >= n:
                break

            # overlap：下一块从 end-overlap 起，并对齐到换行，避免切词
            nstart = end - overlap
            if overlap > 0:
                nxt = text.find("\n", nstart)
                if nxt != -1 and nxt < end:
                    nstart = nxt + 1
            start = max(nstart, start + 1)  # 保证前进，防死循环
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
                    chunks.append(TextChunk(text=buf.strip(), index=idx, token_estimate=_approx_tokens(buf.strip())))
                    idx += 1
                    chunks.append(TextChunk(text=part, index=idx, token_estimate=_approx_tokens(part)))
                    idx += 1
                    buf = ""
                    continue
                else:
                    buf = part
            else:
                if buf.strip():
                    chunks.append(TextChunk(text=buf.strip(), index=idx, token_estimate=_approx_tokens(buf.strip())))
                    idx += 1
                buf = part

        if buf.strip():
            chunks.append(TextChunk(text=buf.strip(), index=idx, token_estimate=_approx_tokens(buf.strip())))

        return chunks or [TextChunk(text="\n\n".join(parts), index=0, token_estimate=_approx_tokens("\n\n".join(parts)))]

    @staticmethod
    def _any_in_limit(parts: list[str], limit: int) -> bool:
        return any(len(p) <= limit for p in parts if p.strip())
