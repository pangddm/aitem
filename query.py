import requests

res = requests.post(
    "http://127.0.0.1:8000/chat",
    json={"message": "你好,KubeDoctor！我在我的 Kubernetes 集群中遇到了一个问题，Pod 一直处于 CrashLoopBackOff 状态。你能帮我分析一下可能的原因并给出修复建议吗？"}
)

print(res.status_code)
print(res.text)