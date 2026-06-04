from app.tools.k8s_tools import run_kubectl_command

async def list_pods(namespace = "default"):
    cmd = f"kubectl get pods -n {namespace}"

    return run_kubectl_command(cmd)