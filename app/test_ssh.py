from app.tools.ssh_client import execute_command

result = execute_command("kubectl get pods")

print(result)