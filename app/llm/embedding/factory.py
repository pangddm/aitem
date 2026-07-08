from app.core.config import EMBEDDING_PROVIDER

from .bge import BGEEmbedding
from .openai import OpenAIEmbedding
from .jina import JinaEmbedding


def get_embedding():

    if EMBEDDING_PROVIDER == "bge":

        return BGEEmbedding()

    if EMBEDDING_PROVIDER == "openai":

        return OpenAIEmbedding()
    if EMBEDDING_PROVIDER == "jina":
        return JinaEmbedding()