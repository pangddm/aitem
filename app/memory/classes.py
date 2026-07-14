from __future__ import annotations


from dataclasses import dataclass, field

from datetime import datetime, timezone

from typing import Dict, List, Optional, Any

from enum import Enum



class MemoryType(str, Enum):

    PREFERENCE = "preference"

    KNOWLEDGE = "knowledge"

    EXPERIENCE = "experience"

    DOCUMENT = "document"

    CLUSTER_STATE = "cluster_state"

    FAULT = "fault"

    SUMMARY = "summary"



class MemorySource(str, Enum):

    CHAT = "chat"

    TOOL = "tool"

    DOCUMENT = "document"

    SYSTEM = "system"

    K8S = "k8s"

    PROMETHEUS = "prometheus"



@dataclass
class CandidateMemory:

    """
    LLM Extractor产生的临时Memory

    不进入数据库

    不包含:

    - id
    - created_at
    - updated_at

    """

    type: MemoryType

    content: str

    summary: Optional[str]

    source: MemorySource

    entities: List[str] = field(
        default_factory=list
    )

    importance: float = 0.5

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class MemoryStats:

    usage_count: int = 0

    last_recalled_at: Optional[datetime] = None

    last_updated_at: Optional[datetime] = None

    last_feedback: Optional[str] = None

    reinforcement_score: float = 0.0



@dataclass
class Memory:

    """
    长期Memory对象

    对应PostgreSQL记录

    """

    id: str

    owner: str

    type: MemoryType

    content: str

    summary: Optional[str]

    source: MemorySource

    entities: List[str]

    importance: float

    metadata: Dict[str, Any]

    created_at: datetime

    updated_at: datetime

    similarity: float | None = None