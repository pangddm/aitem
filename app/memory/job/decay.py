from __future__ import annotations

from datetime import datetime, timezone

from app.memory.repository.memory_repository import (
    MemoryRepository
)

from app.memory.repository.graph_repository import (
    GraphRepository
)

from app.memory.classes import MemoryType



class MemoryDecayJob:


    """
    Memory生命周期管理

    负责:

    1. importance衰减
    2. 低价值Memory删除
    3. PostgreSQL + Neo4j同步删除

    不负责:

    - 新Memory生成
    - Memory更新
    """


    def __init__(

        self,

        memory_repository: MemoryRepository,

        graph_repository: GraphRepository,

        delete_threshold: float = 0.05,

    ):


        self.memory_repository = memory_repository

        self.graph_repository = graph_repository

        self.delete_threshold = delete_threshold



    async def run(self) -> dict:


        """
        执行一次Decay任务

        返回统计信息
        """


        decay_count = await self._decay_importance()


        deleted_count = await self._remove_expired()


        return {

            "decayed": decay_count,

            "deleted": deleted_count,

            "time":
                datetime.now(
                    timezone.utc
                ).isoformat()

        }



    async def _decay_importance(self) -> int:


        """
        根据Memory类型进行衰减

        """

        decay_rates = {


            MemoryType.PREFERENCE: 0.995,


            MemoryType.KNOWLEDGE: 0.995,


            MemoryType.EXPERIENCE: 0.990,


            MemoryType.DOCUMENT: 0.990,


            MemoryType.CLUSTER_STATE: 0.950,


            MemoryType.FAULT: 0.998,


            MemoryType.SUMMARY: 0.985,

        }


        count = 0


        for memory_type, rate in decay_rates.items():


            updated = await (
                self.memory_repository
                .decay_by_type(
                    memory_type=memory_type.value,
                    rate=rate,
                )
            )


            count += updated


        return count



    async def _remove_expired(self) -> int:


        """
        删除低重要性Memory

        流程:

        PostgreSQL查找

        ↓

        Neo4j删除关系

        ↓

        PostgreSQL删除


        """


        memories = await (
            self.memory_repository
            .list_below_importance(
                self.delete_threshold
            )
        )


        deleted = 0


        for memory in memories:


            await (
                self.graph_repository
                .delete_memory_graph(
                    memory.id
                )
            )


            await (
                self.memory_repository
                .delete(
                    memory.id
                )
            )


            deleted += 1


        return deleted