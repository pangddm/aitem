from __future__ import annotations

from datetime import datetime, timezone

from app.memory.entity.normalizer import EntityNormalizer
from app.memory.classes import (
    CandidateMemory,
    Memory,
    MemoryType,
)

from app.memory.merge import (
    MemoryMerger
)

from app.memory.repository.memory_repository import (
    MemoryRepository
)

from app.memory.repository.graph_repository import (
    GraphRepository
)

from app.memory.repository.vector_retriever import (
    VectorRetriever
)

from app.llm.embedding.factory import (
    get_embedding
)


class MemoryUpdater:
    """
    Memory生命周期更新器

    负责:
        CandidateMemory → 判断新增/更新/忽略 → 持久化（PostgreSQL + Neo4j）

    错误处理策略:
        PostgreSQL 写入成功后，Neo4j 写入失败不会回滚 PostgreSQL（因为不是分布式事务）。
        而是标记 metadata.sync_failed.neo4j = error_message，由补偿任务重试。
    """

    def __init__(
        self,
        repository: MemoryRepository,
        retriever: VectorRetriever,
        graph_repository: GraphRepository,
    ):
        self.entity_normalizer = EntityNormalizer()
        self.repository = repository
        self.retriever = retriever
        self.graph_repository = graph_repository
        self.embedding = get_embedding()
        self.merger = MemoryMerger()

    async def update(
        self,
        owner: str,
        candidates: list[CandidateMemory],
    ) -> dict:
        stats = {"insert": 0, "update": 0, "ignore": 0}

        for candidate in candidates:
            if not self._should_persist(candidate):
                stats["ignore"] += 1
                continue

            action = await self._process_one(owner, candidate)
            stats[action] += 1

        return stats

    def _type_weight_boost(self, memory_type: MemoryType) -> float:
        if memory_type == MemoryType.PREFERENCE:
            return 0.12
        if memory_type == MemoryType.KNOWLEDGE:
            return 0.08
        if memory_type == MemoryType.EXPERIENCE:
            return 0.07
        if memory_type == MemoryType.FAULT:
            return 0.09
        return 0.05

    def _should_persist(self, candidate: CandidateMemory) -> bool:
        if not candidate.content or not candidate.content.strip():
            return False
        if candidate.importance >= 0.45:
            return True
        if len(candidate.content) < 20:
            return False
        if any(keyword in candidate.content for keyword in ["优先", "必须", "故障", "异常", "问题", "偏好", "环境", "结论", "记住", "保留"]):
            return True
        return False

    async def _sync_neo4j(self, memory: Memory, action: str) -> None:
        """同步 Memory 到 Neo4j，失败时标记 sync_failed"""
        try:
            if action == "insert":
                await self.graph_repository.insert_memory_graph(memory)
            elif action == "update":
                await self.graph_repository.update_memory_graph(memory)
        except Exception as e:
            print(f"[MemoryUpdater] Neo4j sync failed ({action}) for memory {memory.id}: {e}")
            try:
                await self.repository.mark_sync_failed(
                    memory_id=memory.id,
                    sync_target="neo4j",
                    error=str(e),
                )
            except Exception as mark_err:
                print(f"[MemoryUpdater] Failed to mark sync_failed: {mark_err}")

    async def _process_one(
        self,
        owner: str,
        candidate: CandidateMemory,
    ) -> str:
        # =========================
        # 1. Embedding
        # =========================
        candidate.entities = self.entity_normalizer.normalize(candidate.entities)
        vector = await self.embedding.embed(candidate.content)

        # =========================
        # 2. Vector Retrieve
        # =========================
        memories = await self.retriever.retrieve(
            owner=owner,
            embedding=vector,
            top_k=5,
        )

        # =========================
        # 3. Merge Decision
        # =========================
        result = await self.merger.merge(candidate, memories)

        # =========================
        # 4. Insert
        # =========================
        if result.action == "insert":
            candidate.metadata.setdefault("reinforcement", {})
            candidate.metadata["reinforcement"]["usage_count"] = 1
            candidate.metadata["reinforcement"]["last_recalled_at"] = datetime.now(timezone.utc).isoformat()
            candidate.metadata["reinforcement"]["last_feedback"] = "initial"

            memory = await self.repository.insert_candidate(
                owner=owner,
                candidate=candidate,
                embedding=vector,
            )

            await self._sync_neo4j(memory, "insert")
            return "insert"

        # =========================
        # 5. Update
        # =========================
        if result.action == "update":
            if result.target is None:
                return "ignore"

            candidate.metadata.setdefault("reinforcement", {})
            reinforcement = candidate.metadata["reinforcement"]
            reinforcement["usage_count"] = int(reinforcement.get("usage_count", 0)) + 1
            reinforcement["last_recalled_at"] = datetime.now(timezone.utc).isoformat()
            reinforcement["last_feedback"] = reinforcement.get("last_feedback", "update")

            if reinforcement.get("needs_revision"):
                candidate.importance = max(0.0, candidate.importance - 0.25)
                reinforcement["last_feedback"] = "correction"
                reinforcement["needs_revision"] = True

                await self.repository.mark_superseded(
                    memory_id=result.target.id,
                    superseded_by="correction",
                )

                try:
                    await self.graph_repository.mark_memory_superseded(
                        memory_id=result.target.id,
                        superseded_by="correction",
                    )
                except Exception as e:
                    print(f"[MemoryUpdater] Neo4j mark_superseded failed: {e}")

                corrected_memory = await self.repository.insert_candidate(
                    owner=owner,
                    candidate=candidate,
                    embedding=vector,
                )

                await self._sync_neo4j(corrected_memory, "insert")

                try:
                    await self.graph_repository.link_memory_replacement(
                        old_memory_id=result.target.id,
                        new_memory_id=corrected_memory.id,
                        reason=reinforcement.get("last_feedback", "correction"),
                        version=2,
                        replaced_at=datetime.now(timezone.utc).isoformat(),
                        owner=owner,
                    )
                except Exception as e:
                    print(f"[MemoryUpdater] Neo4j link_replacement failed: {e}")

                return "update"

            base_importance = candidate.importance
            type_boost = self._type_weight_boost(candidate.type)
            reinforcement_boost = 0.05 * max(1, int(reinforcement.get("usage_count", 1)))
            candidate.importance = min(1.0, base_importance + type_boost + reinforcement_boost)

            memory = await self.repository.update_candidate(
                memory_id=result.target.id,
                candidate=candidate,
                embedding=vector,
            )

            await self._sync_neo4j(memory, "update")
            return "update"

        # =========================
        # 6. Ignore
        # =========================
        return "ignore"