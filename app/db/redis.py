"""
Redis 客户端单例

统一管理 Redis 连接，避免各模块重复创建。
支持同步操作（项目当前使用同步 redis 库）。
"""
import os
import redis

from dotenv import load_dotenv

load_dotenv()


class RedisClient:
    """Redis 单例客户端"""

    def __init__(self):
        self._client: redis.Redis | None = None

    @property
    def client(self) -> redis.Redis:
        """获取同步 Redis 客户端（懒加载）"""
        if self._client is None:
            self._client = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", "6379")),
                password=os.getenv("REDIS_PASSWORD", None),
                db=int(os.getenv("REDIS_DB", "0")),
                decode_responses=True,
            )
        return self._client

    def ping(self) -> bool:
        """测试连通性"""
        try:
            return self.client.ping()
        except Exception:
            return False

    def close(self):
        if self._client is not None:
            self._client.close()
            self._client = None


# 全局单例
redis_client = RedisClient()

# 向后兼容：旧代码中 `from app.memory.short_term import r` 的引用
r = redis_client.client