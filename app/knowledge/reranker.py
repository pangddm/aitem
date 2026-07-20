from __future__ import annotations

import json

from app.knowledge.models import Incident
from app.prompt.knowledge_prompt import RERANK_PROMPT


class Reranker:

    def __init__(
        self,
        llm_client,
        model: str = "deepseek-v4-flash",
    ):
        self.client = llm_client
        self.model = model

    async def rerank(
        self,
        query: str,
        incidents: list[Incident],
        top_k: int = 3,
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

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
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
            ],
            temperature=0,
        )

        content = response.choices[0].message.content.strip()

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