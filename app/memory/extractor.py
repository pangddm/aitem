from __future__ import annotations

import json
import re

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.llm.client import get_client
from app.core.config import EXTRACT_MODEL

from app.prompt.memory import MEMORY_EXTRACT_PROMPT

from app.memory.classes import (
    CandidateMemory,
    MemoryType,
    MemorySource,
)



# ============================
# LLM输出结构
# ============================


class MemoryItem(BaseModel):

    type: str

    content: str

    summary: str | None = None

    entities: list[str] = Field(
        default_factory=list
    )

    importance: float = 0.5

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )



class MemoryExtractResponse(BaseModel):

    memories: list[MemoryItem]



# ============================
# Extractor
# ============================


class MemoryExtractor:


    def __init__(

        self,

        model: str = EXTRACT_MODEL,

    ):

        self.model = model



    async def extract(

        self,

        messages: list[dict],

        source: MemorySource = MemorySource.CHAT,

    ) -> list[CandidateMemory]:


        response = await self._call_llm(
            messages
        )

        print("LLM Response:")
        print(response)

        parsed = self._parse_response(
            response,
            source
        )

        if parsed:

            parsed = [
                self._apply_reinforcement_rules(item, messages)
                for item in parsed
            ]

            filtered = [item for item in parsed if self._should_keep_memory(item)]
            print("Filtered memory candidates:", filtered)
            return filtered

        # 提取不到就不再兜底存原文：避免把整段对话原文当成长期记忆，
        # 也避免原文噪音挤掉真正有用的偏好/知识记忆
        print("No memory extracted, skip storing (no raw-text fallback).")
        return []



    async def _call_llm(

        self,

        messages: list[dict],

    ) -> str:


        llm_messages = [

            {

                "role":"system",

                "content":
                MEMORY_EXTRACT_PROMPT

            },

            {

                "role":"user",

                "content":
                json.dumps(
                    messages,
                    ensure_ascii=False,
                    indent=2
                )

            }

        ]


        response = await (
            get_client().chat.completions.create(

                model=self.model,

                messages=llm_messages,

                response_format={
                    "type":"json_object"
                }

            )
        )


        return response.choices[0].message.content



    def _parse_response(

        self,

        response: str,

        source: MemorySource,

    ) -> list[CandidateMemory]:


        try:

            parsed = (
                MemoryExtractResponse
                .model_validate_json(
                    response
                )
            )


        except ValidationError as e:

            print(
                "MemoryExtractor validation error:",
                e
            )

            return []


        except Exception as e:

            print(
                "MemoryExtractor parse error:",
                e
            )

            return []



        memories = []


        for item in parsed.memories:


            memories.append(

                self._build_candidate(

                    item,

                    source

                )

            )


        return memories



    def _build_candidate(

        self,

        item: MemoryItem,

        source: MemorySource,

    ) -> CandidateMemory:


        return CandidateMemory(

            type=self._validate_type(
                item.type
            ),

            content=item.content.strip(),

            summary=item.summary,

            source=source,

            entities=self._normalize_entities(
                item.entities
            ),

            importance=self._normalize_importance(
                item.importance
            ),

            metadata=self._normalize_metadata(
                item.metadata
            ),

        )



    def _is_trivial_message(self, text: str) -> bool:

        if not text:

            return True

        cleaned = re.sub(r"\s+", "", text).strip().lower()

        if not cleaned:

            return True

        if len(cleaned) <= 4:

            return True

        trivial_markers = (
            "你好",
            "hello",
            "hi",
            "ok",
            "好的",
            "谢谢",
            "thanks",
            "再见",
            "bye",
            "在吗",
            "帮我看一下",
        )

        return any(cleaned.startswith(marker) for marker in trivial_markers)


    def _apply_reinforcement_rules(

        self,

        item: CandidateMemory | MemoryItem,
        messages: list[dict],
    ) -> CandidateMemory | MemoryItem:

        if isinstance(item, MemoryItem):

            candidate = self._build_candidate(item, MemorySource.CHAT)

        else:

            candidate = item

        content = (candidate.content or "").strip()

        if not content:

            return candidate

        repeated = self._count_repeated_emphasis(messages, content)

        if repeated > 0:

            candidate.importance = min(1.0, candidate.importance + 0.08 * repeated)

        if self._looks_important(content):

            candidate.importance = min(1.0, candidate.importance + 0.1)

        if self._contains_constraint(content):

            candidate.importance = min(1.0, candidate.importance + 0.08)

        if self._contains_problem_statement(content):

            candidate.importance = min(1.0, candidate.importance + 0.06)

        correction = self._detect_correction(messages, content)

        if correction:

            candidate.importance = max(0.0, candidate.importance - 0.25)
            candidate.metadata.setdefault("reinforcement", {})
            candidate.metadata["reinforcement"]["last_feedback"] = correction
            candidate.metadata["reinforcement"]["feedback_type"] = "correction"
            candidate.metadata["reinforcement"]["needs_revision"] = True

        candidate.metadata.setdefault("reinforcement", {})
        candidate.metadata["reinforcement"]["last_seen_at"] = datetime.now(timezone.utc).isoformat()
        candidate.metadata["reinforcement"]["repetition_count"] = repeated

        return candidate


    def _count_repeated_emphasis(self, messages: list[dict], content: str) -> int:

        if not content:

            return 0

        lower_content = content.lower()
        count = 0

        for item in messages:

            if not isinstance(item, dict):

                continue

            role = item.get("role")
            text = item.get("content")

            if role != "user" or not isinstance(text, str):

                continue

            if lower_content in text.lower():

                count += 1

        return count


    def _looks_important(self, text: str) -> bool:

        keywords = [
            "必须",
            "一定",
            "不要",
            "请",
            "记住",
            "重点",
            "优先",
            "重要",
            "以后",
            "每次",
            "一直",
            "持续",
            "总是",
        ]

        lower = text.lower()

        return any(keyword in lower for keyword in keywords)


    def _contains_constraint(self, text: str) -> bool:

        lower = text.lower()

        return any(token in lower for token in ["不要", "必须", "只能", "优先", "必须要"])


    def _contains_problem_statement(self, text: str) -> bool:

        lower = text.lower()

        return any(token in lower for token in ["故障", "异常", "报错", "挂了", "失败", "问题", "卡住"])

    def _looks_like_transient_operation(self, text: str) -> bool:
        lower = text.lower()
        transient_markers = [
            "已缩容",
            "已扩容",
            "已删除",
            "成功删掉",
            "已执行",
            "现在集群中的 pod",
            "pod 名称",
            "状态",
            "运行中",
            "已完成",
            "还有其他需要吗",
            "可以继续",
        ]
        return any(marker in lower for marker in transient_markers)

    def _detect_correction(self, messages: list[dict], content: str) -> str | None:

        lower_content = content.lower()

        correction_patterns = [
            "不是",
            "不对",
            "错了",
            "改主意",
            "我改主意了",
            "不需要",
            "不要这样",
            "我不想",
        ]

        for item in messages:

            if not isinstance(item, dict):

                continue

            if item.get("role") != "user":

                continue

            text = item.get("content")

            if not isinstance(text, str):

                continue

            lower_text = text.lower()

            if any(pattern in lower_text for pattern in correction_patterns):

                if lower_content in lower_text or lower_text.startswith("不是") or "不对" in lower_text:

                    return "correction"

        return None


    def _should_keep_memory(self, item: CandidateMemory | MemoryItem) -> bool:

        if isinstance(item, CandidateMemory):

            importance = getattr(item, "importance", 0.0) or 0.0
            content = getattr(item, "content", "") or ""

        else:

            importance = getattr(item, "importance", 0.0) or 0.0
            content = getattr(item, "content", "") or ""

        if not content.strip():

            return False

        if self._is_trivial_message(content):

            return False

        if importance < 0.45:
            if len(content) < 20:
                return False
            if any(keyword in content for keyword in ["优先", "必须", "故障", "异常", "问题", "偏好", "环境", "结论", "记住", "保留"]):
                return True
            return False

        if self._looks_like_transient_operation(content):
            return False

        return True


    def _fallback_extract_from_messages(

        self,

        messages: list[dict],

        source: MemorySource,
    ) -> list[CandidateMemory]:

        candidate_messages = []

        for item in messages:

            if not isinstance(item, dict):

                continue

            role = item.get("role")
            content = item.get("content")

            if role not in {"user", "assistant"}:

                continue

            if not isinstance(content, str):

                continue

            text = content.strip()

            if not text or self._is_trivial_message(text):

                continue

            candidate_messages.append(f"{role}: {text}")

        if not candidate_messages:

            return []

        combined = " | ".join(candidate_messages[-2:])
        content = combined[:220]

        if len(content) >= 220:

            content = content.rstrip() + "..."

        return [
            CandidateMemory(
                type=MemoryType.SUMMARY,
                content=content,
                summary="对话中的关键事实与结论摘要",
                source=source,
                entities=[],
                importance=0.7,
                metadata={"source": "fallback"},
            )
        ]


    def _validate_type(

        self,

        value: str,

    ) -> MemoryType:


        try:

            return MemoryType(value)

        except Exception:

            return MemoryType.KNOWLEDGE



    def _normalize_importance(

        self,

        value: float,

    ) -> float:


        return max(
            0.0,
            min(
                1.0,
                float(value)
            )
        )



    def _normalize_entities(

        self,

        entities: list[str],

    ) -> list[str]:


        result = []


        for entity in entities:


            entity = entity.strip()


            if entity:

                result.append(entity)


        return list(
            set(result)
        )



    def _normalize_metadata(

        self,

        metadata: dict[str, Any],

    ) -> dict[str, Any]:


        return metadata or {}