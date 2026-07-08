from __future__ import annotations

import json

from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.llm.client import client

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

        model: str = "deepseek-v4-flash",

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

        return self._parse_response(
            response,
            source
        )



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
            client.chat.completions.create(

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