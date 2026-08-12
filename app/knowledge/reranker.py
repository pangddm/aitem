from __future__ import annotations

import asyncio
import json

from app.knowledge.models import Incident
from app.prompt.knowledge_prompt import RERANK_PROMPT
from app.core.config import RAG_RERANK_TOP_K, RERANK_MODEL, RERANK_FALLBACK_MODEL
from app.core.retry import retry_async


class Reranker:

    def __init__(
        self,
        llm_client,
        model: str = RERANK_MODEL,
    ):
        self.client = llm_client
        self.model = model
        self.fallback_model = RERANK_FALLBACK_MODEL

    def _models(self):
        models = [self.model]
        if self.fallback_model and self.fallback_model != self.model:
            models.append(self.fallback_model)
        return models

    async def _call(self, messages):
        last_exc = None
        for model in self._models():
            try:
                return await retry_async(
                    lambda: self.client.chat.completions.create(
                        model=model, messages=messages, temperature=0,
                    )
                )
            except Exception as e:
                last_exc = e
                continue
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("全部精排模型调用失败")

    async def rerank(
        self,
        query: str,
        incidents: list[Incident],
        top_k: int = RAG_RERANK_TOP_K,
    ) -> list[Incident]:

        if not incidents:
            return []

        if len(incidents) <= top_k:
            return incidents

        cases = []

        for index, incident in enumerate(incidents):

            cases.append(
                {
                    "id": index,
                    "title": incident.title,
                    "summary": incident.summary,
                    "symptom": incident.symptom,
                    "root_cause": incident.root_cause,
                    "solution": incident.solution,
                }
            )

        # 精排调用大模型可能失败/超时，失败时回退到原始候选，避免整条 RAG 检索变空
        try:
            response = await self._call(
                [
                    {
                        "role": "system",
                        "content": RERANK_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "query": query,
                                "cases": cases,
                                "top_k": top_k,
                            },
                            ensure_ascii=False,
                        ),
                    },
                ]
            )
            content = response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[Reranker] 精排调用失败，回退到原始候选: {type(e).__name__}: {e}")
            return incidents[:top_k]

        try:

            result = json.loads(content)

            order = result["ranking"]

        except Exception:

            return incidents[:top_k]

        outputs = []

        for idx in order:

            if 0 <= idx < len(incidents):

                outputs.append(
                    incidents[idx]
                )

        if not outputs:

            return incidents[:top_k]

        return outputs[:top_k]

class CrossEncoderReranker:
    """本地 cross-encoder 重排：比 LLM 精排快且便宜。

    用 sentence-transformers CrossEncoder 对 (query, 候选) 逐对打分。
    模型懒加载并缓存；打分是阻塞调用，通过 asyncio.to_thread 避免阻塞事件循环。
    """

    def __init__(
        self,
        model_name: str | None = None,
        top_k: int = RAG_RERANK_TOP_K,
    ):
        from app.core.config import CROSS_ENCODER_MODEL

        self.model_name = model_name or CROSS_ENCODER_MODEL
        self.top_k = top_k
        self._model = None

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(
                self.model_name,
                max_length=512,
                device="cpu",
            )
        return self._model

    @staticmethod
    def _pair_text(incident: Incident) -> str:
        parts = [
            f"标题: {incident.title}",
        ]
        if incident.summary:
            parts.append(f"摘要: {incident.summary}")
        if incident.symptom:
            parts.append(f"现象: {incident.symptom}")
        if incident.solution:
            parts.append(f"方案: {incident.solution}")
        return " ".join(parts)

    async def rerank(
        self,
        query: str,
        incidents: list[Incident],
        top_k: int = RAG_RERANK_TOP_K,
    ) -> list[Incident]:

        if not incidents:
            return []

        if len(incidents) <= top_k:
            return incidents

        model = self._load_model()
        pairs = [(query, self._pair_text(inc)) for inc in incidents]

        # 阻塞打分放到线程池，避免卡事件循环
        scores = await asyncio.to_thread(self._score_pairs, model, pairs)

        # 带原下标的降序排序（不稳定时以 scores 为准）
        ranked = sorted(
            zip(incidents, scores),
            key=lambda t: t[1],
            reverse=True,
        )
        return [inc for inc, _ in ranked[:top_k]]

    @staticmethod
    def _score_pairs(model, pairs):
        return model.predict(
            pairs,
            show_progress_bar=False,
        )
