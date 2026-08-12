"""通用异步重试：指数退避 + 抖动，支持按异常类型决定是否重试。"""
from __future__ import annotations

import asyncio
import functools
import random
from typing import Awaitable, Callable, Optional, TypeVar

from app.core.config import (
    API_RETRY_ATTEMPTS,
    API_RETRY_BASE_DELAY,
    API_RETRY_MAX_DELAY,
)

T = TypeVar("T")

# httpx 可重试的 HTTP 状态码
RETRYABLE_HTTP_CODES = (429, 500, 502, 503, 504)


def is_retryable(exc: Exception) -> bool:
    """判断异常是否值得重试（网络/超时/限流/5xx）。"""
    try:
        import httpx
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in RETRYABLE_HTTP_CODES
        if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
            return True
    except Exception:
        pass

    try:
        import openai
        base = (openai.APIError,)
        if isinstance(exc, base):
            # APIStatusError 有 status_code；RateLimit 429 / 内部 5xx / 连接错误
            if isinstance(exc, openai.APIStatusError):
                return exc.status_code in RETRYABLE_HTTP_CODES
            if isinstance(exc, (openai.APIConnectionError, openai.APITimeoutError, openai.Timeout)):
                return True
    except Exception:
        pass

    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, ConnectionError, OSError)):
        return True
    return False


async def retry_async(
    coro_factory: Callable[[], Awaitable[T]],
    *,
    attempts: Optional[int] = None,
    base_delay: Optional[float] = None,
    max_delay: Optional[float] = None,
    retry_on: Callable[[Exception], bool] = is_retryable,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
) -> T:
    """对返回协程的工厂重试，指数退避 + 抖动。

    attempts 用尽或异常不可重试时抛最后一次异常。
    """
    attempts = attempts or API_RETRY_ATTEMPTS
    if attempts < 1:
        attempts = 1
    base_delay = API_RETRY_BASE_DELAY if base_delay is None else base_delay
    max_delay = API_RETRY_MAX_DELAY if max_delay is None else max_delay

    delay = base_delay
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return await coro_factory()
        except Exception as e:
            last_exc = e
            if attempt == attempts - 1:
                break
            if not retry_on(e):
                break
            if on_retry:
                on_retry(attempt, e)
            jitter = 1.0 + random.random() * 0.4
            await asyncio.sleep(delay * jitter)
            delay = min(delay * 2, max_delay)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("retry_async: 未捕获异常")


def retry_sync(
    fn,
    *,
    attempts: int | None = None,
    base_delay: float | None = None,
    max_delay: float | None = None,
    retry_on=is_retryable,
    on_retry=None,
):
    """同步版重试（指数退避 + 抖动），供非异步调用使用。"""
    import time

    attempts = attempts or API_RETRY_ATTEMPTS
    if attempts < 1:
        attempts = 1
    base_delay = API_RETRY_BASE_DELAY if base_delay is None else base_delay
    max_delay = API_RETRY_MAX_DELAY if max_delay is None else max_delay

    delay = base_delay
    last_exc = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if attempt == attempts - 1:
                break
            if not retry_on(e):
                break
            if on_retry:
                on_retry(attempt, e)
            time.sleep(delay * (1.0 + random.random() * 0.4))
            delay = min(delay * 2, max_delay)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("retry_sync: 未捕获异常")


def is_db_retryable(exc: Exception) -> bool:
    """判断是否为 DB 瞬时错误（连接丢失/死锁/序列化冲突/网络层）。"""
    try:
        import asyncpg

        names = (
            "PostgresConnectionError",
            "ConnectionDoesNotExistError",
            "DeadlockDetectedError",
            "SerializationError",
            "OperationalError",
        )
        transient = tuple(
            getattr(asyncpg.exceptions, n)
            for n in names
            if hasattr(asyncpg.exceptions, n)
        )
        if transient and isinstance(exc, transient):
            return True
    except Exception:
        pass

    try:
        import neo4j
        from neo4j.exceptions import (
            ServiceUnavailable,
            SessionExpired,
            TransientError,
        )
        if isinstance(
            exc, (ServiceUnavailable, SessionExpired, TransientError)
        ):
            return True
    except Exception:
        pass

    if isinstance(exc, (ConnectionError, OSError, TimeoutError)):
        return True
    return False


async def retry_db(coro_factory, attempts: int | None = None):
    """对 DB 操作重试（瞬时错误），每次重试重新执行并重新取连接。"""
    from app.core.config import DB_RETRY_ATTEMPTS

    return await retry_async(
        coro_factory,
        attempts=attempts if attempts is not None else DB_RETRY_ATTEMPTS,
        retry_on=is_db_retryable,
    )


def db_retry(func):
    """装饰器：对 DB 写方法包裹重试，瞬时错误自动退避重试。

    用法:
        @db_retry
        async def create(...): ...
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return await retry_db(lambda: func(*args, **kwargs))
    return wrapper
