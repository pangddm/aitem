import requests

res = requests.post(
    "http://127.0.0.1:8000/chat",
    json={"message": "帮我查看当前所有 Pod"}
)

print(res.status_code)
print(res.text)