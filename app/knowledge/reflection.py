from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

from app.knowledge.embedding import EmbeddingService
from app.knowledge.models import (
    CommandTrace,
    Incident,
    IncidentSource,
)
from app.knowledge.repository.incident_repository import (
    IncidentRepository,
)
from app.prompt.knowledge_prompt import REFLECTION_PROMPT


class ReflectionService:

    def __init__(
        self,
        llm_client,
        embedding_service: EmbeddingService,
        incident_repository: IncidentRepository,
        model: str = "deepseek-v4-flash",
    ):
        self.client = llm_client
        self.embedding_service = embedding_service
        self.incident_repository = incident_repository
        self.model = model

    async def reflect(
        self,
        kb_id: str,
        user_question: str,
        final_answer: str,
        tool_history: list[dict],
        owner: str = "default",
    ) -> Incident | None:

        if not tool_history:
            return None

        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": REFLECTION_PROMPT,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": user_question,
                            "answer": final_answer,
                            "tool_history": tool_history,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        )

        content = response.choices[0].message.content.strip()

        try:
            result = json.loads(content)
        except Exception:
            return None

        commands = []

        for item in result.get(
            "commands",
            [],
        ):

            commands.append(
                CommandTrace(
                    command=item.get(
                        "command",
                        "",
                    ),
                    stdout=item.get(
                        "stdout",
                        "",
                    ),
                    stderr=item.get(
                        "stderr",
                        "",
                    ),
                    exit_code=item.get(
                        "exit_code",
                        0,
                    ),
                )
            )

        incident = Incident(

            id=str(uuid4()),

            owner=owner,

            kb_id=kb_id,

            document_id=None,

            source=IncidentSource.LEARNING,

            title=result.get(
                "title",
                "",
            ),

            summary=result.get(
                "summary",
                "",
            ),

            symptom=result.get(
                "symptom",
                "",
            ),

            root_cause=result.get(
                "root_cause",
                "",
            ),

            solution=result.get(
                "solution",
                "",
            ),

            environment=result.get(
                "environment",
                {},
            ),

            commands=commands,

            metadata={},

            created_at=datetime.utcnow(),

            updated_at=datetime.utcnow(),
        )

        embedding_text = self.embedding_service.build_incident_text(

            title=incident.title,

            summary=incident.summary,

            symptom=incident.symptom,

            root_cause=incident.root_cause,

            solution=incident.solution,
        )

        incident.embedding = await self.embedding_service.embed(
            embedding_text
        )

        await self.incident_repository.create(
            incident
        )

        return incident