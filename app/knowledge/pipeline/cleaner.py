import re

# 代码块标记
_CODE_BLOCK = re.compile(r"```[\s\S]*?```", re.MULTILINE)
# 表格行：至少含 2 个制表符或多个连续空格分隔
_TABLE_ROW = re.compile(r".*\t{2,}.*")       # 至少2个tab → xlsx表格
_TABLE_SPACE = re.compile(r"\S {2,}\S")       # 至少2个连续空格 → 对齐表格


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

        # ── 逐行处理 ──
        lines = text.split("\n")
        cleaned = []
        for line in lines:
            # 表格行：保留原始格式（tab 或对齐空格）
            if _TABLE_ROW.match(line) or _TABLE_SPACE.match(line):
                cleaned.append(line.rstrip())
            else:
                cleaned.append(line.rstrip())

        text = "\n".join(cleaned)

        # ── 合并多余空行（仅对非代码块区域） ──
        text = re.sub(r"\n{3,}", "\n\n", text)

        # ── 恢复代码块 ──
        for i, block in enumerate(code_blocks):
            text = text.replace(f"__CODE_BLOCK_{i}__", block)

        # ── 对纯文本段落轻量去前后空白 ──
        # 不做 [ \t]+ → 的全文替换，保留表格/代码结构

        return text.strip()