from __future__ import annotations


import json

from dataclasses import dataclass
from typing import Literal, Optional


from app.llm.client import client

from app.memory.classes import Memory

from app.memory.models.candidate import CandidateMemory



@dataclass
class MergeResult:


    action: Literal[
        "insert",
        "update",
        "ignore"
    ]


    target: Optional[Memory] = None


    reason: str = ""



class MemoryMerger:


    def __init__(

        self,

        model="deepseek-v4-flash",

    ):

        self.model=model



    async def merge(

        self,

        candidate: CandidateMemory,

        memories: list[Memory],

    )->MergeResult:



        if not memories:

            return MergeResult(

                action="insert",

                reason="no similar memory"

            )


        result = await self._ask_llm(

            candidate,

            memories

        )


        return self._parse_result(

            result,

            memories

        )



    async def _ask_llm(

        self,

        candidate: CandidateMemory,

        memories:list[Memory],

    ):



        existing = []


        for memory in memories:


            existing.append(

                {

                    "id":memory.id,

                    "type":memory.type.value,

                    "content":memory.content,

                    "summary":memory.summary,

                    "importance":memory.importance,

                }

            )



        prompt = f"""

                你是一个Memory管理系统。

                判断新的候选记忆是否应该合并已有记忆。


                新记忆:

                {json.dumps(

                {

                "type":candidate.type.value,

                "content":candidate.content,

                "summary":candidate.summary

                },

                ensure_ascii=False

                )}



                已有记忆:

                {json.dumps(

                existing,

                ensure_ascii=False

                )}



                请返回JSON:


                {{

                "action":

                "insert | update | ignore",


                "target_id":

                "如果update，需要填写目标memory id，否则为空",


                "reason":

                "原因"

                }}

                """


        response = await client.chat.completions.create(

            model=self.model,

            messages=[

                {

                    "role":"system",

                    "content":
                    "You are a memory merge engine."

                },

                {

                    "role":"user",

                    "content":prompt

                }

            ],

            response_format={

                "type":"json_object"

            }

        )


        return response.choices[0].message.content




    def _parse_result(

        self,

        result:str,

        memories:list[Memory],

    )->MergeResult:



        data=json.loads(result)


        action=data.get(
            "action",
            "insert"
        )


        target_id=data.get(
            "target_id"
        )


        target=None


        if target_id:


            for memory in memories:


                if memory.id==target_id:

                    target=memory

                    break



        return MergeResult(

            action=action,

            target=target,

            reason=data.get(
                "reason",
                ""
            )

        )