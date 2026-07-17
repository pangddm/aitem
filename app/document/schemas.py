from pydantic import BaseModel
from typing import Optional


class DocumentChunk(BaseModel):

    type: str

    content: str

    source: str

    metadata: dict = {}