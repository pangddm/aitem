import requests

res = requests.post(
    "http://127.0.0.1:8000/chat",
    json={
        "user_id": "wxm",
        "message": "我喜欢用啥命令，docker还是nerdctl呢",}
)

print(res.status_code)
print(res.text)