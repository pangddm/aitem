"""
思考链 (Chain-of-Thought) HTML 生成器

用 <a> 锚点 + display toggle 实现折叠（QTextEdit 不支持 <details>）。
"""

from html import escape


def build_cot_html(cot_id: str, reasoning: str, tool_calls: list[dict],
                   expanded: set | None = None, streaming: bool = False) -> str:
    """生成思考链 HTML。
    
    Args:
        cot_id: 唯一标识
        reasoning: 思考链文本（可能已截取）
        tool_calls: 工具调用列表
        expanded: 已展开的 toggle key 集合
        streaming: True 表示正在流式展示（不显示展开/收起按钮）
    """
    if not reasoning and not tool_calls:
        return ""

    if expanded is None:
        expanded = set()

    parts = []

    if reasoning or tool_calls:
        key = f"{cot_id}-reasoning"
        is_open = key in (expanded or set())

        if streaming:
            # 流式：只显示最后 4 行（滚动刷新效果）
            lines = reasoning.split("\n")
            show_lines = lines[-4:] if len(lines) > 4 else lines
            safe = escape("\n".join(show_lines)).replace("\n", "<br>")

            # 工具调用嵌入同一滚动区域
            trows = ""
            if tool_calls:
                trows = '<div style="margin-top:6px;padding-top:4px;border-top:1px solid #334155;">'
                for tc in tool_calls:
                    trows += f"""<div style="margin:2px 0;padding:3px 6px;background:#0f172a;border-radius:3px;">
                        <span style="color:#60a5fa;font-weight:600;font-size:11px;">🔧 {escape(tc.get('tool','?'))}</span>
                        <code style="color:#cbd5e1;font-size:10px;margin-left:4px;">{escape(tc.get('command','')[:80])}</code>
                        <span style="color:#64748b;font-size:10px;margin-left:4px;">→ {escape(tc.get('result','')[:100])}</span>
                    </div>"""
                trows += '</div>'

            parts.append(f"""
            <div style="margin:2px 0;">
                <div style="color:#fbbf24;font-weight:600;font-size:12px;margin-bottom:2px;">
                    🤔 思考中...
                </div>
                <div style="background:#1a1f2e;border-left:3px solid #fbbf24;border-radius:6px;
                            padding:8px 12px;font-size:12px;color:#94a3b8;
                            max-height:180px;overflow-y:auto;line-height:1.5;">
                    {safe}
                    {trows}
                </div>
            </div>
            """)

        elif is_open:
            safe = escape(reasoning).replace("\n", "<br>")
            if len(safe) > 8000:
                safe = safe[:8000] + "<br>...（已截断）"
            # 工具调用在展开时也放进去
            trows = ""
            if tool_calls:
                trows = '<div style="margin-top:8px;padding-top:6px;border-top:1px solid #334155;">'
                for tc in tool_calls:
                    trows += f"""<div style="margin:3px 0;padding:4px 8px;background:#0f172a;border-radius:4px;">
                        <span style="color:#60a5fa;font-weight:600;font-size:11px;">🔧 {escape(tc.get('tool','?'))}</span>
                        <code style="color:#cbd5e1;font-size:10px;margin-left:6px;">{escape(tc.get('command','')[:100])}</code>
                        <div style="color:#64748b;font-size:10px;margin-top:2px;">{escape(tc.get('result','')[:200])}</div>
                    </div>"""
                trows += '</div>'
            parts.append(f"""
            <div style="margin:2px 0;">
                <a href="#toggle-{key}" style="color:#fbbf24;font-weight:600;font-size:12px;text-decoration:none;">
                    🤔 思考过程 ▾ 收起
                </a>
                <div style="background:#1a1f2e;border-left:3px solid #fbbf24;border-radius:6px;
                            padding:8px 12px;margin-top:4px;font-size:12px;color:#94a3b8;
                            max-height:300px;overflow-y:auto;line-height:1.5;">
                    {safe}
                    {trows}
                </div>
            </div>
            """)

        else:
            # 折叠
            lines_count = reasoning.count("\n") + 1 if reasoning else 0
            tc_hint = f" | 🔧 {len(tool_calls)} 次工具调用" if tool_calls else ""
            parts.append(f"""
            <div style="margin:2px 0;">
                <a href="#toggle-{key}" style="color:#fbbf24;font-weight:600;font-size:12px;text-decoration:none;">
                    🤔 思考过程 ▸ 展开 ({lines_count} 行{tc_hint})
                </a>
            </div>
            """)

    return f"""
    <div style="margin:6px 0;display:flex;justify-content:flex-start;animation:fadeInUp 0.28s ease;">
        <div style="max-width:85%;background:#111827;border:1px solid #1f2937;border-radius:14px;padding:8px 14px;">
            {''.join(parts)}
        </div>
    </div>"""
