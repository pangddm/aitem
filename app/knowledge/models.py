from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ==========================================================
# Enum
# ==========================================================

class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class IncidentSource(str, Enum):
    UPLOAD = "upload"          # 用户上传文档生成
    LEARNING = "learning"      # Agent 自动学习生成
    MANUAL = "manual"          # 用户手动创建


class KnowledgeCategory(str, Enum):
    """知识条目的分类"""

    FAULT = "fault"              # 故障排障
    PERFORMANCE = "performance"  # 性能测试
    CONFIG = "config"            # 配置参考
    CHANGE = "change"            # 变更记录
    DOC = "doc"                  # 通用文档


# ==========================================================
# Knowledge Base
# ==========================================================

@dataclass(slots=True)
class KnowledgeBase:
    """
    一个用户可以拥有多个知识库
    """

    id: str

    owner: str

    name: str

    description: str | None = None

    is_public: bool = False

    created_at: datetime | None = None

    updated_at: datetime | None = None


# ==========================================================
# Document
# ==========================================================

@dataclass(slots=True)
class Document:
    """
    上传的原始文档
    """

    id: str

    owner: str

    kb_id: str

    filename: str

    mime_type: str

    file_size: int

    source: str

    origin_text: str

    ocr_text: str

    content_hash: str | None = None

    parse_status: DocumentStatus = DocumentStatus.PENDING

    metadata: dict[str, Any] = field(default_factory=dict)

    created_at: datetime | None = None

    updated_at: datetime | None = None


# ==========================================================
# Command Trace
# ==========================================================

@dataclass(slots=True)
class CommandTrace:
    """
    一条执行命令
    """

    command: str

    stdout: str = ""

    stderr: str = ""

    exit_code: int = 0


# ==========================================================
# Incident
# ==========================================================

@dataclass(slots=True)
class Incident:
    """
    一条可复用的运维知识条目

    category 决定字段语义：
      - fault:       symptom=故障现象, root_cause=根因,    solution=解决方案
      - performance: symptom=测试目的, root_cause=测试结论, solution=优化建议
      - config:      symptom=配置用途, root_cause=注意事项, solution=配置内容
      - change:      symptom=变更内容, root_cause=影响范围, solution=回滚方案
      - doc:         symptom=文档主题, root_cause=关键发现, solution=参考价值
    """

    id: str

    owner: str

    kb_id: str

    document_id: str | None

    source: IncidentSource

    title: str

    summary: str

    symptom: str

    root_cause: str

    solution: str

    category: KnowledgeCategory = KnowledgeCategory.DOC

    # Parent-Child Chunking: child=Incident 本身, parent=原始章节全文
    context_text: str = ""

    keywords: list[str] = field(default_factory=list)

    environment: dict[str, Any] = field(default_factory=dict)

    commands: list[CommandTrace] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    embedding: list[float] | None = None

    score: float | None = None

    created_at: datetime | None = None

    updated_at: datetime | None = None


# ==========================================================
# Search Result
# ==========================================================

@dataclass(slots=True)
class SearchResult:

    incident: Incident

    score: float