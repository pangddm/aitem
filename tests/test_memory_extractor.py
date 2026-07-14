import unittest

from app.memory.classes import CandidateMemory, MemoryType, MemorySource
from app.memory.extractor import MemoryExtractor
from app.memory.updater import MemoryUpdater


class MemoryExtractorTests(unittest.TestCase):
    def test_should_keep_memory_for_meaningful_summary_with_modest_importance(self):
        extractor = MemoryExtractor()
        candidate = CandidateMemory(
            type=MemoryType.KNOWLEDGE,
            content="用户希望在生产环境中优先保留 nginx 的故障排查结论",
            summary="用户强调保留故障排查结论",
            source=MemorySource.CHAT,
            importance=0.55,
        )

        self.assertTrue(extractor._should_keep_memory(candidate))

    def test_should_persist_preference_memory_with_high_importance(self):
        updater = object.__new__(MemoryUpdater)
        candidate = CandidateMemory(
            type=MemoryType.PREFERENCE,
            content="用户以后优先使用 nginx 做故障排查",
            summary="用户偏好用 nginx 做故障排查",
            source=MemorySource.CHAT,
            importance=0.9,
        )

        self.assertTrue(updater._should_persist(candidate))

    def test_should_persist_knowledge_memory_with_high_importance(self):
        updater = object.__new__(MemoryUpdater)
        candidate = CandidateMemory(
            type=MemoryType.KNOWLEDGE,
            content="生产环境中的 nginx 配置需要特别注意连接数",
            summary="生产环境 nginx 配置要注意连接数",
            source=MemorySource.CHAT,
            importance=0.9,
        )

        self.assertTrue(updater._should_persist(candidate))


if __name__ == "__main__":
    unittest.main()
