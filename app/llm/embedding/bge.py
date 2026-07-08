from sentence_transformers import SentenceTransformer

from .base import EmbeddingModel


class BGEEmbedding(EmbeddingModel):

    def __init__(self):

        self.model = SentenceTransformer(
            "BAAI/bge-m3"
        )

    async def embed(
        self,
        text: str
    ) -> list[float]:

        return self.model.encode(
            text,
            normalize_embeddings=True
        ).tolist()