from __future__ import annotations

import json
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
from app.core.config import EXTRACT_MODEL


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

            commands = []

            for cmd in item.get(
                "commands",
                [],
            ):

                commands.append(

                    CommandTrace(

                        command=cmd.get(
                            "command",
                            "",
                        ),

                        stdout=cmd.get(
                            "stdout",
                            "",
                        ),

                        stderr=cmd.get(
                            "stderr",
                            "",
                        ),

                        exit_code=cmd.get(
                            "exit_code",
                            0,
                        ),
                    )
                )

            incidents.append(

                Incident(

                    id=str(uuid4()),

                    owner=owner,

                    kb_id=kb_id,

                    document_id=document_id,

                    source=IncidentSource.UPLOAD,

                    category=self._parse_category(
                        item.get("category", "doc")
                    ),

                    title=item.get(
                        "title",
                        "",
                    ),

                    summary=item.get(
                        "summary",
                        "",
                    ),

                    symptom=item.get(
                        "symptom",
                        "",
                    ),

                    root_cause=item.get(
                        "root_cause",
                        "",
                    ),

                    solution=item.get(
                        "solution",
                        "",
                    ),

                    environment=item.get(
                        "environment",
                        {},
                    ),

                    commands=commands,

                    metadata={},
                )
            )

        return incidents

    async def _llm_extract(
        self,
        text: str,
    ) -> list[dict] | None:

        try:
            response = await self.client.chat.completions.create(
                model=EXTRACT_MODEL,
                messages=[
                    {"role": "system", "content": EXTRACT_INCIDENT_PROMPT},
                    {"role": "user", "content": text},
                ],
                timeout=120,  # 2分钟超时
            )

            content = response.choices[0].message.content
            items = json.loads(content)

            if isinstance(items, list) and len(items) > 0:
                return items
        except Exception:
            pass

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
        if any(
            kw in lower
            for kw in ["故障", "error", "exception", "fail", "crash"]
        ):
            cat = "fault"
        elif any(
            kw in lower
            for kw in [
                "性能", "压测", "benchmark",
                "qps", "tps", "latency",
            ]
        ):
            cat = "performance"
        elif any(
            kw in lower
            for kw in ["配置", "config", "nginx", "yaml"]
        ):
            cat = "config"
        elif any(
            kw in lower
            for kw in ["变更", "上线", "发布", "deploy", "rollback"]
        ):
            cat = "change"
        else:
            cat = "doc"

        return {
            "category": cat,
            "title": title,
            "summary": summary,
            "symptom": (
                "故障现象" if cat == "fault" else "文档内容"
            ),
            "root_cause": "",
            "solution": "",
            "environment": {},
            "commands": [],
        }