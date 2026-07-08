from __future__ import annotations


from datetime import datetime, timezone


from app.memory.MemoryExtractor import (
    MemoryExtractor
)

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


        messages = await (
            self.redis
            .lrange(
                key,
                0,
                -1
            )
        )


        if not messages:

            return



        offset_key = (

            f"memory_offset:"
            f"{conversation_id}"

        )


        processed = await (
            self.redis
            .get(
                offset_key
            )
        )


        processed = int(
            processed or 0
        )



        # 已经处理过

        if processed >= len(messages):

            return



        new_messages = messages[processed:]



        await self.memory_service.process(

            owner=owner,

            messages=new_messages,

        )



        await self.redis.set(

            offset_key,

            len(messages),

        )