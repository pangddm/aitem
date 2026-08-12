"""文本清洗：在保留代码/表格结构的前提下做轻量归一化与去敏。"""
import re

from app.core.config import CLEANER_MASK_SENSITIVE

# 代码块标记
_CODE_BLOCK = re.compile(r"```[\s\S]*?```", re.MULTILINE)
# 表格行：至少含 2 个制表符或多个连续空格分隔
_TABLE_ROW = re.compile(r".*\t{2,}.*")       # 至少2个tab → xlsx表格
_TABLE_SPACE = re.compile(r"\S {2,}\S")       # 至少2个连续空格 → 对齐表格

# ── 全角 → 半角 ──
_FULLWIDTH = str.maketrans({
    **{chr(0xFF01 + i): chr(0x21 + i) for i in range(0x5E)},  # 全角标点/ASCII
    "\u3000": " ",  # 全角空格
    "：": ":",
    "；": ";",
    "，": ",",
    "。": ".",
    "（": "(",
    "）": ")",
})

# ── 敏感信息掩码 ──
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_KEYVALUE_RE = re.compile(
    r"((?:api[_-]?key|token|secret|passwd|password|access[_-]?key)"
    r"\s*[=:]\s*)\S{8,}",
    re.IGNORECASE,
)
_LONG_HEX_RE = re.compile(r"\b[0-9a-fA-F]{32,}\b")
_LONG_B64_RE = re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b")


class TextCleaner:

    def clean(
        self,
        text: str,
    ) -> str:

        text = text.replace("\r", "")

        # ── 保护代码块 ──
        code_blocks = []

        def _save_code(m):
            code_blocks.append(m.group(0))
            return f"__CODE_BLOCK_{len(code_blocks) - 1}__"

        text = _CODE_BLOCK.sub(_save_code, text)

        # ── 全角 → 半角（代码块保护区外） ──
        text = text.translate(_FULLWIDTH)

        # ── 敏感信息掩码 ──
        if CLEANER_MASK_SENSITIVE:
            text = _mask_sensitive(text)

        # ── 逐行处理 ──
        lines = text.split("\n")
        cleaned = []
        for line in lines:
            # 表格行保留原始分隔（xlsx 用 tab、对齐表格用多空格），避免破坏列结构
            if _TABLE_ROW.match(line) or _TABLE_SPACE.match(line):
                cleaned.append(line.rstrip())
            else:
                # 普通行：仅折叠 2+ 连续空格，保留 tab（避免破坏 xlsx/tab 分隔）
                cleaned.append(re.sub(r" {2,}", " ", line).rstrip())

        text = "\n".join(cleaned)

        # ── 合并多余空行（仅对非代码块区域） ──
        text = re.sub(r"\n{3,}", "\n\n", text)

        # ── 恢复代码块 ──
        for i, block in enumerate(code_blocks):
            text = text.replace(f"__CODE_BLOCK_{i}__", block)

        return text.strip()


def _mask_sensitive(text: str) -> str:
    # 先掩码 key=value 形式的凭据（优先），再掩码长串/邮箱/URL
    text = _KEYVALUE_RE.sub(lambda m: m.group(1) + "[MASKED]", text)
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _URL_RE.sub("[URL]", text)
    text = _LONG_B64_RE.sub("[SECRET]", text)
    text = _LONG_HEX_RE.sub("[SECRET]", text)
    return text
