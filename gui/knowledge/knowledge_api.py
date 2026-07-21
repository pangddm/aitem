"""
知识库 API 客户端（与 gui/api.py 解耦）

所有知识库相关的 HTTP 请求集中在此模块。
"""

from __future__ import annotations

import os

import requests

BASE_URL = "http://127.0.0.1:8000"


# ──────────────────────────────────────────────
#  知识库 CRUD
# ──────────────────────────────────────────────


def create_kb(owner: str, name: str, description: str = "") -> dict:
    """创建知识库"""
    res = requests.post(
        f"{BASE_URL}/knowledge/kb",
        data={
            "owner": owner,
            "name": name,
            "description": description,
        },
        timeout=10,
    )
    return res.json()


def list_kbs(owner: str) -> dict:
    """列出用户的所有知识库"""
    res = requests.get(
        f"{BASE_URL}/knowledge/kb/list",
        params={"owner": owner},
        timeout=10,
    )
    return res.json()


def get_kb(kb_id: str) -> dict:
    """获取知识库详情"""
    res = requests.get(
        f"{BASE_URL}/knowledge/kb/{kb_id}",
        timeout=10,
    )
    return res.json()


def delete_kb(kb_id: str) -> dict:
    """删除知识库"""
    res = requests.delete(
        f"{BASE_URL}/knowledge/kb/{kb_id}",
        timeout=10,
    )
    return res.json()


# ──────────────────────────────────────────────
#  文档上传
# ──────────────────────────────────────────────


def upload_document(kb_id: str, owner: str, file_path: str) -> dict:
    """上传单个文档到知识库（异步，返回 document_id）"""
    filename = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        res = requests.post(
            f"{BASE_URL}/knowledge/kb/{kb_id}/upload",
            files={"file": (filename, f, "application/octet-stream")},
            data={"owner": owner},
            timeout=30,  # 只等文件传输，不等处理
        )
    return res.json()


def get_document_status(document_id: str) -> dict:
    """轮询文档处理进度"""
    try:
        res = requests.get(
            f"{BASE_URL}/knowledge/document/{document_id}/status",
            timeout=5,
        )
        return res.json()
    except Exception:
        return {"success": False, "stage": "", "message": "连接失败"}


def upload_text(kb_id: str, owner: str, filename: str, text: str) -> dict:
    """直接粘贴文本到知识库"""
    res = requests.post(
        f"{BASE_URL}/knowledge/kb/{kb_id}/text",
        data={
            "owner": owner,
            "filename": filename,
            "text": text,
        },
        timeout=120,
    )
    return res.json()


# ──────────────────────────────────────────────
#  批量上传
# ──────────────────────────────────────────────


def batch_upload(kb_id: str, owner: str, file_paths: list[str]) -> dict:
    """批量上传多个文档到知识库"""
    files = []
    for fp in file_paths:
        filename = os.path.basename(fp)
        files.append(("files", (filename, open(fp, "rb"), "application/octet-stream")))

    try:
        res = requests.post(
            f"{BASE_URL}/knowledge/kb/{kb_id}/batch-upload",
            files=files,
            data={"owner": owner},
            timeout=600,
        )
        return res.json()
    finally:
        # 确保所有文件句柄关闭
        for _, item in files:
            item[1].close()


# ──────────────────────────────────────────────
#  检索 & 统计
# ──────────────────────────────────────────────


def search_kb(kb_id: str, query: str, top_k: int = 3) -> dict:
    """在知识库中检索"""
    res = requests.get(
        f"{BASE_URL}/knowledge/kb/{kb_id}/search",
        params={"query": query, "top_k": top_k},
        timeout=30,
    )
    return res.json()


def get_kb_stats(kb_id: str) -> dict:
    """获取知识库统计信息"""
    res = requests.get(
        f"{BASE_URL}/knowledge/kb/{kb_id}/stats",
        timeout=10,
    )
    return res.json()


def list_incidents(kb_id: str, page: int = 1, page_size: int = 20) -> dict:
    """分页列出案例"""
    res = requests.get(
        f"{BASE_URL}/knowledge/kb/{kb_id}/incidents",
        params={"page": page, "page_size": page_size},
        timeout=10,
    )
    return res.json()
