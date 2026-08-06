from app.core.config import EMBEDDING_PROVIDER

from .bge import BGEEmbedding
from .openai import OpenAIEmbedding
from .jina import JinaEmbedding
from .dashscope import DashScopeEmbedding
from .failover import FailoverEmbedding


def get_embedding():

    if EMBEDDING_PROVIDER == "bge":

        return BGEEmbedding()

    if EMBEDDING_PROVIDER == "openai":

        return OpenAIEmbedding()
    if EMBEDDING_PROVIDER == "dashscope":
        return DashScopeEmbedding()
    # 无论配置是 jina 还是 hybrid，都使用"Jina 优先、超时/失败自动切阿里云"的容错
    if EMBEDDING_PROVIDER in ("jina", "hybrid"):
        return FailoverEmbedding(primary=JinaEmbedding(), fallback=DashScopeEmbedding())
