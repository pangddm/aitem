from sentence_transformers import SentenceTransformer

from app.core.config import BGE_MODEL

from .base import EmbeddingModel


class BGEEmbedding(EmbeddingModel):

    def __init__(self):

        self.model = SentenceTransformer(
            BGE_MODEL
        )

    async def embed(
        self,
        text: str
    ) -> list[float]:

        return self.model.encode(
            text,
            normalize_embeddings=True
        ).tolist()