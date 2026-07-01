import requests

res = requests.post(
    "http://127.0.0.1:8000/chat",
    json={
        "user_id": "wxm",
        "message": "现在我们是第几轮对话了？",}
)

print(res.status_code)
print(res.text)