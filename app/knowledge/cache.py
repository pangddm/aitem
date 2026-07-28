"""
检索缓存模块

优化点:
1. Embedding 缓存：相同 query 的 embedding 结果缓存，避免重复调用 API
2. 检索结果缓存：相同 (kb_id, query, top_k) 的检索结果缓存，避免重复检索
3. 缓存命中率统计：便于监控缓存效果
4. 细粒度 TTL 控制：高频查询缓存更久，低频查询缓存更短

使用 Redis 作为缓存后端
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from app.db.redis import redis_client


class RetrievalCache:
    """检索缓存"""

    # Embedding 缓存 TTL: 24 小时（embedding 不变）
    EMBEDDING_TTL = 86400

    # 检索结果缓存 TTL: 1 小时（知识库可能更新）
    SEARCH_TTL = 3600

    # 高频查询缓存 TTL: 4 小时（常见问题缓存更久）
    HOT_SEARCH_TTL = 14400

    # 缓存命中率统计
    _stats = {"embedding_hits": 0, "embedding_misses": 0,
              "search_hits": 0, "search_misses": 0}

    @staticmethod
    def _hash_key(text: str) -> str:
        """生成缓存 key"""
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    # ==========================================================
    # 缓存统计
    # ==========================================================

    def get_stats(self) -> dict:
        """获取缓存命中率统计"""
        total_emb = self._stats["embedding_hits"] + self._stats["embedding_misses"]
        total_search = self._stats["search_hits"] + self._stats["search_misses"]
        return {
            "embedding": {
                "hits": self._stats["embedding_hits"],
                "misses": self._stats["embedding_misses"],
                "hit_rate": round(self._stats["embedding_hits"] / total_emb, 4) if total_emb > 0 else 0,
            },
            "search": {
                "hits": self._stats["search_hits"],
                "misses": self._stats["search_misses"],
                "hit_rate": round(self._stats["search_hits"] / total_search, 4) if total_search > 0 else 0,
            },
        }

    def reset_stats(self):
        """重置统计"""
        self._stats = {"embedding_hits": 0, "embedding_misses": 0,
                       "search_hits": 0, "search_misses": 0}

    # ==========================================================
    # Embedding 缓存
    # ==========================================================

    def get_embedding(self, text: str) -> list[float] | None:
        """获取缓存的 embedding"""
        try:
            key = f"emb:{self._hash_key(text)}"
            cached = redis_client.client.get(key)
            if cached:
                self._stats["embedding_hits"] += 1
                return json.loads(cached)
        except Exception:
            pass
        self._stats["embedding_misses"] += 1
        return None

    def set_embedding(
        self, text: str, embedding: list[float]
    ) -> None:
        """缓存 embedding"""
        try:
            key = f"emb:{self._hash_key(text)}"
            redis_client.client.setex(
                key, self.EMBEDDING_TTL, json.dumps(embedding)
            )
        except Exception:
            pass

    # ==========================================================
    # 检索结果缓存
    # ==========================================================

    def get_search(
        self, kb_id: str, query: str, top_k: int
    ) -> list[dict] | None:
        """获取缓存的检索结果"""
        try:
            key = f"search:{kb_id}:{self._hash_key(query)}:{top_k}"
            cached = redis_client.client.get(key)
            if cached:
                self._stats["search_hits"] += 1
                return json.loads(cached)
        except Exception:
            pass
        self._stats["search_misses"] += 1
        return None

    def set_search(
        self,
        kb_id: str,
        query: str,
        top_k: int,
        results: list[dict],
        is_hot_query: bool = False,
    ) -> None:
        """
        缓存检索结果

        优化: 高频查询使用更长的 TTL
        Args:
            is_hot_query: 是否为高频查询（常见问题），是则缓存 4 小时
        """
        try:
            key = f"search:{kb_id}:{self._hash_key(query)}:{top_k}"
            ttl = self.HOT_SEARCH_TTL if is_hot_query else self.SEARCH_TTL
            redis_client.client.setex(
                key, ttl, json.dumps(results)
            )
        except Exception:
            pass

    # ==========================================================
    # 失效缓存（知识库更新时调用）
    # ==========================================================

    def invalidate_kb(self, kb_id: str) -> None:
        """失效某个知识库的所有检索缓存"""
        try:
            # 使用 SCAN 避免阻塞 Redis
            deleted = 0
            for key in redis_client.client.scan_iter(
                f"search:{kb_id}:*"
            ):
                redis_client.client.delete(key)
                deleted += 1
            if deleted > 0:
                print(f"[Cache] 失效知识库 {kb_id} 的 {deleted} 条检索缓存")
        except Exception:
            pass


# 全局单例
retrieval_cache = RetrievalCache()
