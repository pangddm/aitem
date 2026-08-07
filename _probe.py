import os
os.chdir(r"D:\desktop\aitem")
from app.tools.ssh_client import execute_command
from app.core.config import TARGET_HOST, TARGET_PORT
print("TARGET:", TARGET_HOST, TARGET_PORT)
for cmd in ["hostname; whoami", "kubectl version --client 2>/dev/null || echo NO_KUBECTL", "kubectl get nodes -o wide 2>&1 | head -20"]:
    print("=== CMD:", cmd)
    try:
        print(execute_command(cmd))
    except Exception as e:
        print("FAILED:", type(e).__name__, e)