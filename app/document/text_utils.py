"""文本读取：UTF-8 优先，失败回退常见编码（GBK/GB18030/Latin-1）。"""
from __future__ import annotations

from pathlib import Path

_FALLBACK_ENCODINGS = ["utf-8", "gbk", "gb18030", "latin-1"]


def read_text(
    file_path: str,
    default_encoding: str = "utf-8",
) -> str:
    data = Path(file_path).read_bytes()

    candidates = [default_encoding] + _FALLBACK_ENCODINGS
    seen: set[str] = set()
    order: list[str] = []
    for enc in candidates:
        if enc not in seen:
            seen.add(enc)
            order.append(enc)

    for enc in order:
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue

    # 都不行：丢无法解码的字节，保证不抛异常
    return data.decode("utf-8", errors="replace")
