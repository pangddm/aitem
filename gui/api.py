import requests


BASE_URL = "http://127.0.0.1:8000"


def login(username, password):

    res = requests.post(
        f"{BASE_URL}/login",
        json={
            "username": username,
            "password": password
        },
        timeout=10
    )

    return res.json()



def chat(user_id, message):

    res = requests.post(
        f"{BASE_URL}/chat",
        json={
            "user_id": user_id,
            "message": message
        },
        timeout=120
    )

    return res.json()

def register(username, password):

    res = requests.post(
        f"{BASE_URL}/register",
        json={
            "username": username,
            "password": password
        },
        timeout=10
    )

    return res.json()


def upload_document(owner: str, file_path: str):
    """上传文档到后端"""
    import os
    filename = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        res = requests.post(
            f"{BASE_URL}/document/upload",
            files={"file": (filename, f, "application/octet-stream")},
            data={"owner": owner},
            timeout=120
        )
    return res.json()


def chat_with_document(user_id: str, message: str, file_path: str):
    """同时发送文档+文字消息，后端提取文档后与 DeepSeek 问答"""
    import os
    filename = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        res = requests.post(
            f"{BASE_URL}/chat_with_document",
            files={"file": (filename, f, "application/octet-stream")},
            data={
                "user_id": user_id,
                "message": message,
            },
            timeout=300
        )
    return res.json()