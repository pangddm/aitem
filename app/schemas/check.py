"""
命令安全检查 — 黑名单模式
"""

# 禁止的危险关键字
DENY_KEYWORDS = [
    "rm ",
    "rmdir",
    "replace",
    "edit",
    "exec",
    "cp",
    "port-forward",
    "drain",
    "sudo",
    "mv ",
    "chmod",
    "chown",
    "shutdown",
    "reboot",
    "systemctl",
    "scp",
    "&&",
    ";",
    ">",
    "<",
    "$(",
    "`"
]


def is_safe_command(cmd: str) -> bool:
    cmd_lower = cmd.strip().lower()
    for keyword in DENY_KEYWORDS:
        if keyword in cmd_lower:
            return False
    return True