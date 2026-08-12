"""检索融合：RRF（倒数排名融合）在纯逻辑层实现，便于测试。"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable


def rrf_fuse(
    vector_results: list,
    keyword_results: list,
    k: int = 60,
    top_k: int | None = None,
):
    """把向量召回与关键词召回按 RRF 融合。

    score(item) = sum over lists of 1 / (k + rank), rank 从 1 起。
    返回按融合分降序的列表；元素复用有效，score 字段被更新。
    """
    acc: dict[str, float] = defaultdict(float)
    ranked: dict[str, object] = {}

    def _accumulate(results):
        for rank, item in enumerate(results, start=1):
            key = getattr(item, "id", None) or id(item)
            acc[key] += 1.0 / (k + rank)
            ranked[key] = item

    _accumulate(vector_results or [])
    _accumulate(keyword_results or [])

    ordered = sorted(
        acc.items(),
        key=lambda kv: kv[1],
        reverse=True,
    )

    out = []
    for key, score in ordered:
        item = ranked[key]
        try:
            item.score = score
        except Exception:
            pass
        out.append(item)
        if top_k and len(out) >= top_k:
            break
    return out


def min_score_filter(items: Iterable, threshold: float):
    """按 score 阈值过滤（阈值<=0 时不启用）。"""
    if not threshold or threshold <= 0:
        return list(items)
    return [it for it in items if (getattr(it, "score", 0) or 0) >= threshold]
