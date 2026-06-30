import requests

res = requests.post(
    "http://127.0.0.1:8000/chat",
    json={
        "user_id": "wxm",
        "message": "我上一个问题是什么？"}
)

print(res.status_code)
print(res.text)