"""集中配置：所有可能调整的环境变量统一从 .env 读取并在此暴露。

新增参数时：先在 .env 中定义，再在这个文件里用 os.getenv() 读取并导出。
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _bool(value, default="false"):
    return (value or default).strip().lower() in ("true", "1", "yes", "on")


def _int(value, default):
    try:
        return int(value) if value is not None and str(value).strip() else int(default)
    except (TypeError, ValueError):
        return int(default)


def _float(value, default):
    try:
        return float(value) if value is not None and str(value).strip() else float(default)
    except (TypeError, ValueError):
        return float(default)


# ───────────── 数据库 / 缓存 ─────────────
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = _int(os.getenv("POSTGRES_PORT"), 5432)
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_DB = os.getenv("POSTGRES_DB", "kubedoctor")
POSTGRES_POOL_MIN = _int(os.getenv("POSTGRES_POOL_MIN"), 2)
POSTGRES_POOL_MAX = _int(os.getenv("POSTGRES_POOL_MAX"), 10)

MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = _int(os.getenv("MYSQL_PORT"), 3306)
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "123456")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "Users")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = _int(os.getenv("REDIS_PORT"), 6379)
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None
REDIS_DB = _int(os.getenv("REDIS_DB"), 0)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

# ───────────── Neo4j 写入开关 ─────────────
# 控制「聊天过程中的记忆图 / 工具审计图」写入，默认开启。
# 集群拓扑索引（定时读取集群信息并写入 Neo4j 用于拓扑展示）始终开启，不受此开关影响。
NEO4J_WRITE_ENABLED = _bool(os.getenv("NEO4J_WRITE_ENABLED"), "true")

# ───────────── 大模型 LLM ─────────────
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
# 主模型（自动执行/默认）
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
# 备选模型（主模型失败时自动切换）
DEEPSEEK_FALLBACK_MODEL = os.getenv("DEEPSEEK_FALLBACK_MODEL", "deepseek-reasoner")
# 重排器使用的模型
RERANK_MODEL = os.getenv("RERANK_MODEL", "deepseek-v4-flash")
# 知识抽取/记忆提取等使用的模型
EXTRACT_MODEL = os.getenv("EXTRACT_MODEL", "deepseek-v4-flash")

# ───────────── Embedding 向量化 ─────────────
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "hybrid")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))
EMBEDDING_FAILOVER_TIMEOUT = float(os.getenv("EMBEDDING_FAILOVER_TIMEOUT", "2.0"))
DASHSCOPE_EMBEDDING_BASE_URL = os.getenv(
    "DASHSCOPE_EMBEDDING_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings",
)
DASHSCOPE_EMBEDDING_MODEL = os.getenv("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v4")
JINA_API_KEY = os.getenv("JINA_API_KEY", "")
JINA_BASE_URL = os.getenv("JINA_BASE_URL", "https://api.jina.ai/v1/embeddings")
JINA_MODEL = os.getenv("JINA_MODEL", "jina-embeddings-v5-text-small")
BGE_MODEL = os.getenv("BGE_MODEL", "BAAI/bge-m3")

# ───────────── 视觉/多模态 ─────────────
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
VISION_MODEL = os.getenv("VISION_MODEL", "qwen3.5-397b-a17b")
VISION_BASE_URL = os.getenv(
    "VISION_BASE_URL",
    "https://ws-desdcuc07ogrkiwd.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
)

# ───────────── 邮件告警 SMTP ─────────────
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.163.com")
SMTP_PORT = _int(os.getenv("SMTP_PORT"), 465)
SMTP_SENDER = os.getenv("SMTP_SENDER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_RECEIVER = os.getenv("SMTP_RECEIVER", "")

# ───────────── Agent 工作流参数 ─────────────
# 置信度达到该值以上自动执行（非测试模式）
AUTO_EXEC_CONFIDENCE = _float(os.getenv("AUTO_EXEC_CONFIDENCE"), 0.8)
# Observer → Validator 最大重试轮次
MAX_RETRY_LOOPS = _int(os.getenv("MAX_RETRY_LOOPS"), 2)
# Agent 总迭代次数上限
MAX_AGENT_ITERATIONS = _int(os.getenv("MAX_AGENT_ITERATIONS"), 10)
# 无进展时的强制用户选择阈值（循环保护）
LOOP_NO_PROGRESS_LIMIT = _int(os.getenv("LOOP_NO_PROGRESS_LIMIT"), 3)

# ───────────── 知识库检索 ─────────────
RAG_TOP_K = _int(os.getenv("RAG_TOP_K"), 10)
RAG_RERANK_TOP_K = _int(os.getenv("RAG_RERANK_TOP_K"), 3)
# 是否启用 LLM 精排（开启会明显变慢，失败已自动回退）
ENABLE_RERANK = _bool(os.getenv("ENABLE_RERANK"))

# ───────────── SSH ─────────────
SSH_CONNECT_TIMEOUT = _float(os.getenv("SSH_CONNECT_TIMEOUT"), 8.0)
SSH_TIMEOUT = _int(os.getenv("SSH_TIMEOUT"), 30)
SSH_POOL_MAX_IDLE = _int(os.getenv("SSH_POOL_MAX_IDLE"), 300)
SSH_POOL_CLEAN_INTERVAL = _int(os.getenv("SSH_POOL_CLEAN_INTERVAL"), 60)

# ───────────── 目标主机（SSH 默认连接）─────────────
TARGET_HOST = os.getenv("TARGET_HOST", "")
TARGET_PORT = _int(os.getenv("TARGET_PORT"), 22)
TARGET_USERNAME = os.getenv("TARGET_USERNAME", "")
TARGET_PASSWORD = os.getenv("TARGET_PASSWORD", "")

# ───────────── 运行模式 ─────────────
TEST_MODE = _bool(os.getenv("TEST_MODE"))
# 上传入库成功后是否保留原始文件（默认删除，节省空间）
KEEP_RAW_FILE = _bool(os.getenv("KEEP_RAW_FILE"))
