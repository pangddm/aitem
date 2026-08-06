"""
LLM 客户端 — 支持多模型自动切换
当 flash 模型连接失败时自动切换到 pro 模型
使用线程本地存储避免并发请求互相干扰
"""
import asyncio
import threading
from openai import AsyncOpenAI
from app.core.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    DEEPSEEK_FALLBACK_MODEL,
)

API_KEY = DEEPSEEK_API_KEY

# 模型配置：按优先级排列，连接失败自动切换
MODEL_CONFIGS = [
    {
        "name": DEEPSEEK_MODEL or "deepseek-chat",       # DeepSeek V3 (flash)
        "base_url": DEEPSEEK_BASE_URL,
        "display_name": "DeepSeek Flash",
    },
    {
        "name": DEEPSEEK_FALLBACK_MODEL or "deepseek-reasoner",   # DeepSeek R1 (pro, 有思考链)
        "base_url": DEEPSEEK_BASE_URL,
        "display_name": "DeepSeek Pro",
    },
]

# 每个请求独立的模型状态（线程本地存储）
_request_local = threading.local()


def _get_state():
    """获取当前请求的模型状态，首次访问时初始化"""
    if not hasattr(_request_local, "initialized"):
        _request_local.model_index = 0
        _request_local.failed_models = set()
        _request_local.client = AsyncOpenAI(
            api_key=API_KEY,
            base_url=MODEL_CONFIGS[0]["base_url"],
        )
        _request_local.initialized = True
    return _request_local


def get_client():
    """获取当前请求的 AsyncOpenAI 客户端"""
    return _get_state().client


def get_current_model_name() -> str:
    """获取当前请求使用的模型名称"""
    idx = _get_state().model_index
    return MODEL_CONFIGS[idx]["name"]


def get_current_model_display() -> str:
    """获取当前请求模型的显示名称"""
    idx = _get_state().model_index
    return MODEL_CONFIGS[idx]["display_name"]


def get_model_status() -> list:
    """获取所有模型的状态"""
    state = _get_state()
    status = []
    for i, cfg in enumerate(MODEL_CONFIGS):
        status.append({
            "name": cfg["display_name"],
            "model": cfg["name"],
            "active": i == state.model_index,
            "failed": i in state.failed_models,
        })
    return status


async def switch_to_next_model() -> bool:
    """
    切换到下一个可用模型（仅影响当前请求）
    返回 True 表示切换成功，False 表示所有模型都已失败
    """
    state = _get_state()
    state.failed_models.add(state.model_index)

    # 尝试下一个模型
    for i in range(len(MODEL_CONFIGS)):
        if i not in state.failed_models:
            state.model_index = i
            cfg = MODEL_CONFIGS[i]
            state.client = AsyncOpenAI(
                api_key=API_KEY,
                base_url=cfg["base_url"],
            )
            print(f"[LLM] 切换到模型: {cfg['display_name']} ({cfg['name']})")
            return True

    # 所有模型都失败了，重置并回到第一个
    print("[LLM] 所有模型都失败了，重置状态")
    state.failed_models.clear()
    state.model_index = 0
    cfg = MODEL_CONFIGS[0]
    state.client = AsyncOpenAI(
        api_key=API_KEY,
        base_url=cfg["base_url"],
    )
    return False


def reset_model_state():
    """重置当前请求的模型状态"""
    state = _get_state()
    state.model_index = 0
    state.failed_models.clear()
    state.client = AsyncOpenAI(
        api_key=API_KEY,
        base_url=MODEL_CONFIGS[0]["base_url"],
    )
    print("[LLM] 模型状态已重置")
