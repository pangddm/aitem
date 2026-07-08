from dataclasses import dataclass, field
from typing import Any

from app.memory.classes import MemoryType, MemorySource


@dataclass
class CandidateMemory:

    type: MemoryType

    content: str

    summary: str | None = None

    source: MemorySource = MemorySource.CHAT

    entities: list[str] = field(default_factory=list)

    importance: float = 0.5

    metadata: dict[str, Any] = field(default_factory=dict)