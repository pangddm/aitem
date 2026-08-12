"""知识抽取：从文档文本中提取结构化 Incident，带 JSON 修复与重试。"""
from __future__ import annotations

import json
import re
from uuid import uuid4

from app.knowledge.models import (
    CommandTrace,
    Incident,
    IncidentSource,
    KnowledgeCategory,
)
from app.prompt.knowledge_prompt import (
    EXTRACT_INCIDENT_PROMPT,
)
from app.core.config import EXTRACT_MODEL, EXTRACT_FALLBACK_MODEL, EXTRACT_JSON_RETRY
from app.core.retry import retry_async, is_retryable


def _strip_trailing_commas(text: str) -> str:
    """去除 JSON 中对象/数组结尾多余逗号，增强容错。"""
    return re.sub(r",\s*([}\]])", r"\1", text)


def _parse_items(content: str | None):
    """尽力把 LLM 输出解析成 JSON 数组；失败返回 None。"""
    if not content:
        return None

    raw = content.strip()
    # 1) 直接解析
    try:
        obj = json.loads(raw)
        if isinstance(obj, list):
            return obj
    except Exception:
        pass

    # 2) 去掉 markdown 围栏
    m = re.search(r"```[a-zA-Z]*\s*(.*?)```", raw, re.S)
    if m:
        raw = m.group(1).strip()

    # 3) 取首个 [ 到末个 ]
    i = raw.find("[")
    j = raw.rfind("]")
    if i != -1 and j != -1 and j > i:
        sub = _strip_trailing_commas(raw[i:j + 1])
        try:
            obj = json.loads(sub)
            if isinstance(obj, list):
                return obj
        except Exception:
            pass

    return None


class IncidentExtractor:

    def __init__(
        self,
        llm_client,
    ):
        self.client = llm_client

    async def extract(
        self,
        kb_id: str,
        document_id: str,
        text: str,
        owner: str,
    ) -> list[Incident]:

        items = await self._llm_extract(text)

        if not items:
            items = [self._build_fallback(text)]

        incidents = []

        for item in items:

            if not isinstance(item, dict):
                continue

            commands = []

            for cmd in item.get("commands", []) or []:
                if not isinstance(cmd, dict):
                    continue
                commands.append(
                    CommandTrace(
                        command=str(cmd.get("command", "")),
                        stdout=str(cmd.get("stdout", "")),
                        stderr=str(cmd.get("stderr", "")),
                        exit_code=int(cmd.get("exit_code", 0) or 0),
                    )
                )

            incidents.append(
                Incident(
                    id=str(uuid4()),
                    owner=owner,
                    kb_id=kb_id,
                    document_id=document_id,
                    source=IncidentSource.UPLOAD,
                    category=self._parse_category(item.get("category", "doc")),
                    title=str(item.get("title", "")),
                    summary=str(item.get("summary", "")),
                    symptom=str(item.get("symptom", "")),
                    root_cause=str(item.get("root_cause", "")),
                    solution=str(item.get("solution", "")),
                    environment=item.get("environment", {}) if isinstance(item.get("environment"), dict) else {},
                    commands=commands,
                    metadata={},
                )
            )

        return incidents

    def _models(self):
        models = [EXTRACT_MODEL]
        if EXTRACT_FALLBACK_MODEL and EXTRACT_FALLBACK_MODEL != EXTRACT_MODEL:
            models.append(EXTRACT_FALLBACK_MODEL)
        return models

    async def _generate(self, messages):
        last_exc = None
        for model in self._models():
            try:
                return await retry_async(
                    lambda: self.client.chat.completions.create(
                        model=model, messages=messages, timeout=120,
                    )
                )
            except Exception as e:
                last_exc = e
                continue
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("全部抽取模型调用失败")

    async def _llm_extract(
        self,
        text: str,
    ) -> list[dict] | None:

        last_content: str | None = None
        retries = EXTRACT_JSON_RETRY if EXTRACT_JSON_RETRY and EXTRACT_JSON_RETRY >= 0 else 2

        for attempt in range(retries + 1):
            user_content = text
            if attempt > 0:
                user_content = (
                    text
                    + "\n\n（注意：上一次输出不是合法的纯 JSON 数组。"
                    + "请只输出一个合规的 JSON 数组，字段用双引号，不要输出 markdown 或任何解释文字。）"
                )
            try:
                response = await self._generate(
                    [
                        {"role": "system", "content": EXTRACT_INCIDENT_PROMPT},
                        {"role": "user", "content": user_content},
                    ]
                )
                content = response.choices[0].message.content
                last_content = content
                items = _parse_items(content)
                if isinstance(items, list) and len(items) > 0:
                    return items
            except Exception:
                # 网络瞬断/限流已由 retry_async 退避重试；解析失败走外层重试
                continue

        # 兜底：即便最后一次输出格式不标准，也尽量解析
        if last_content:
            items = _parse_items(last_content)
            if isinstance(items, list) and len(items) > 0:
                return items
        return None

    @staticmethod
    def _parse_category(value: str) -> KnowledgeCategory:
        """解析 category，兼容旧值（deployment/pod/service/network/storage/other）"""
        legacy_map = {
            "deployment": KnowledgeCategory.CHANGE,
            "pod": KnowledgeCategory.FAULT,
            "service": KnowledgeCategory.FAULT,
            "network": KnowledgeCategory.FAULT,
            "storage": KnowledgeCategory.FAULT,
            "other": KnowledgeCategory.DOC,
        }
        try:
            return KnowledgeCategory(value)
        except ValueError:
            return legacy_map.get(value, KnowledgeCategory.DOC)

    @staticmethod
    def _build_fallback(
        text: str,
        max_len: int = 400,
    ) -> dict:
        """
        兜底：从文档内容智能生成一条知识条目。

        不做粗暴截断，而是：
          1. 用首行做标题
          2. 在句号处截断摘要
          3. 根据关键词自动判断文档类型
        """

        lines = [
            line.strip()
            for line in text.split("\n")
            if line.strip()
        ]

        # 标题
        first_line = lines[0] if lines else "未命名文档"
        title = first_line[:120].rstrip("。，,、：:")

        # 摘要：在完整句子处截断
        raw = text.replace("\r", "").replace("\t", " ").strip()
        if len(raw) <= max_len:
            summary = raw
        else:
            cut = raw[:max_len]
            last_period = max(
                cut.rfind("。"),
                cut.rfind("."),
                cut.rfind("\n"),
                cut.rfind("！"),
            )
            if last_period > max_len // 2:
                summary = raw[: last_period + 1]
            else:
                summary = raw[:max_len]

        # 关键词判断类型
        lower = text.lower()
        if any(kw in lower for kw in ["故障", "error", "exception", "fail", "crash"]):
            cat = "fault"
        elif any(kw in lower for kw in ["性能", "压测", "benchmark", "qps", "tps", "latency"]):
            cat = "performance"
        elif any(kw in lower for kw in ["配置", "config", "nginx", "yaml"]):
            cat = "config"
        elif any(kw in lower for kw in ["变更", "上线", "发布", "deploy", "rollback"]):
            cat = "change"
        else:
            cat = "doc"

        return {
            "category": cat,
            "title": title,
            "summary": summary,
            "symptom": "故障现象" if cat == "fault" else "文档内容",
            "root_cause": "",
            "solution": "",
            "environment": {},
            "commands": [],
        }
