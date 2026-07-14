from __future__ import annotations


from datetime import datetime, timezone


import json

from app.memory.memory_service import (
    MemoryService
)



class ShortTermMemoryBridge:



    def __init__(

        self,

        redis_client,

        memory_service: MemoryService,

    ):


        self.redis = redis_client

        self.memory_service = memory_service



    async def process_conversation(

        self,

        owner: str,

        conversation_id: str,

    ):


        """
        Redis短期记忆进入长期记忆

        """


        key = (
            f"conversation:"
            f"{conversation_id}"
        )


        messages = self.redis.lrange(
            key,
            0,
            -1
        )


        if not messages:

            return


        parsed_messages = []

        for item in messages:

            if isinstance(item, str):

                try:

                    parsed_item = json.loads(item)

                except (TypeError, json.JSONDecodeError):

                    parsed_item = {
                        "role": "user",
                        "content": item,
                    }

            else:

                parsed_item = item

            if isinstance(parsed_item, dict):

                role = parsed_item.get("role", "user")
                content = parsed_item.get("content")

                if role in {"user", "assistant"} and isinstance(content, str) and content.strip():

                    parsed_messages.append(parsed_item)



        offset_key = (

            f"memory_offset:"
            f"{conversation_id}"

        )


        processed = self.redis.get(
            offset_key
        )


        processed = int(
            processed or 0
        )



        # 已经处理过

        if processed >= len(parsed_messages):

            return



        new_messages = parsed_messages[processed:]



        await self.memory_service.process(

            owner=owner,

            messages=new_messages,

        )



        self.redis.set(

            offset_key,

            len(parsed_messages),

        )