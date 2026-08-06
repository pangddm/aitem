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

    错误处理:
        Neo4j 删除失败不会阻止 PostgreSQL 删除（避免孤儿数据留在主库）。
        Neo4j 中的残留节点由补偿任务清理。
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
        """执行一次Decay任务，返回统计信息"""
        decay_count = await self._decay_importance()
        deleted_count = await self._remove_expired()
        return {
            "decayed": decay_count,
            "deleted": deleted_count,
            "time": datetime.now(timezone.utc).isoformat()
        }

    async def _decay_importance(self) -> int:
        """根据Memory类型进行衰减"""
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
            updated = await self.memory_repository.decay_by_type(
                memory_type=memory_type.value,
                rate=rate,
            )
            count += updated
        return count

    async def _remove_expired(self) -> int:
        """
        删除低重要性Memory

        流程:
            1. PostgreSQL查找低重要性Memory
            2. 尝试Neo4j删除（失败不阻塞）
            3. PostgreSQL删除（主库优先）
        """
        memories = await self.memory_repository.list_below_importance(
            self.delete_threshold
        )

        deleted = 0
        for memory in memories:
            # 先删 Neo4j（失败不阻塞 PostgreSQL 删除）
            try:
                await self.graph_repository.delete_memory_graph(memory.id)
            except Exception as e:
                print(f"[DecayJob] Neo4j delete failed for memory {memory.id}: {e}")
                # 标记同步失败，补偿任务会重试
                try:
                    await self.memory_repository.mark_sync_failed(
                        memory_id=memory.id,
                        sync_target="neo4j_delete",
                        error=str(e),
                    )
                except Exception:
                    pass  # 标记失败也不阻塞主库删除

            # 再删 PostgreSQL（主库优先，确保不产生孤儿数据）
            try:
                await self.memory_repository.delete(memory.id)
                deleted += 1
            except Exception as e:
                print(f"[DecayJob] PostgreSQL delete failed for memory {memory.id}: {e}")

        return deleted