import subprocess

# 允许的命令前缀
ALLOWED_PREFIXES = [
    "kubectl get",
    "kubectl describe",
    "kubectl logs",
    "kubectl top",
    "kubectl version",
    "kubectl api-resources",
    "kubectl cluster-info"
]

# 禁止的危险关键字
DENY_KEYWORDS = [
    "delete",
    "apply",
    "create",
    "patch",
    "replace",
    "edit",
    "exec",
    "cp",
    "port-forward",
    "drain",
    "cordon",
    "uncordon",
    "rollout restart",
    "scale",
    "sudo",
    "rm",
    "mv",
    "chmod",
    "chown",
    "shutdown",
    "reboot",
    "systemctl",
    "curl",
    "wget",
    "ssh",
    "scp",
    "&&",
    ";",
    "|",
    ">",
    "<",
    "$(",
    "`"
]

def is_safe_command(cmd: str) -> bool:
    cmd = cmd.strip().lower()

    # 必须以白名单开头
    if not any(cmd.startswith(prefix) for prefix in ALLOWED_PREFIXES):
        return False

    # 不能包含危险关键字
    for keyword in DENY_KEYWORDS:
        if keyword in cmd:
            return False

    return True