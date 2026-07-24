import os
from dotenv import load_dotenv

load_dotenv()

POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT"))
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB = os.getenv("POSTGRES_DB")
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER")
JINA_API_KEY = os.getenv("JINA_API_KEY")
TEST_MODE = os.getenv("TEST_MODE", "false").lower() in ("true", "1", "yes")
