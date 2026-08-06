"""
Redis 客户端单例

统一管理 Redis 连接，避免各模块重复创建。
支持同步操作（项目当前使用同步 redis 库）。
"""
import redis

from app.core.config import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB


class RedisClient:
    """Redis 单例客户端"""

    def __init__(self):
        self._client: redis.Redis | None = None

    @property
    def client(self) -> redis.Redis:
        """获取同步 Redis 客户端（懒加载）"""
        if self._client is None:
            self._client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD,
                db=REDIS_DB,
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