"""
命令安全检查 — 宽松模式（全流程测试用）
"""

import shlex

# 危险命令（按命令名精确匹配，严禁执行）
# 已注释掉，全流程测试阶段允许所有命令
# DANGEROUS_COMMANDS = {
#     "rm", "rmdir", "sudo", "shutdown", "reboot",
#     "systemctl", "chmod", "chown", "mkfs",
#     "dd", "kill", "killall",
# }

# 允许的命令白名单（优先级高于黑名单）
# 已扩展为允许所有命令
ALLOWED_PREFIXES = (
    "kubectl", "docker", "git", "ls", "cat",
    "echo", "grep", "find", "ps", "top",
    "curl", "wget", "ping", "nslookup",
    "rm", "rmdir", "sudo", "shutdown", "reboot",
    "systemctl", "chmod", "chown", "mkfs",
    "dd", "kill", "killall",
    "cd", "pwd", "mkdir", "cp", "mv", "touch",
    "vi", "vim", "nano", "tail", "head", "less", "more",
    "awk", "sed", "sort", "uniq", "wc", "diff",
    "tar", "zip", "unzip", "gzip", "gunzip",
    "ssh", "scp", "rsync",
    "apt", "apt-get", "yum", "dnf", "pip", "npm",
    "python", "python3", "node", "java", "go",
    "systemctl", "journalctl", "dmesg",
    "ip", "ifconfig", "netstat", "ss", "lsof",
    "df", "du", "free", "uptime", "who", "w",
    "crontab", "at",
    "chmod", "chown", "chgrp",
    "useradd", "userdel", "usermod", "groupadd", "groupdel",
    "fdisk", "parted", "mount", "umount",
    "iptables", "firewall-cmd", "ufw",
)

# kubectl 子命令安全规则
# 全流程测试阶段：全部允许
# 值为 True 表示该子命令被完全禁止
# 值为 set 表示该子命令在特定参数组合下被禁止
KUBECTL_SUBCOMMAND_RULES = {
    # 全流程测试阶段：全部允许
    # "drain": True,
    # "delete": {"all", "deployment", "deploy", "svc", "service", "namespace", "ns"},
}


def is_safe_command(cmd: str) -> bool:
    """
    精准检查命令安全性：
    1. 使用 shlex 解析命令，避免子字符串误匹配
    2. 优先匹配白名单前缀
    3. 对 kubectl 子命令做精细检查

    测试模式：跳过所有检查，允许所有命令
    """
    from app.core.config import TEST_MODE
    if TEST_MODE:
        return True
    
    cmd = cmd.strip()
    if not cmd:
        return False

    # 解析命令
    try:
        parts = shlex.split(cmd)
    except ValueError:
        return False

    if not parts:
        return False

    base_cmd = parts[0]

    # 非白名单命令直接拒绝
    if base_cmd not in ALLOWED_PREFIXES:
        return False

    # kubectl 命令精细检查
    if base_cmd == "kubectl" and len(parts) > 1:
        sub_cmd = parts[1]

        # 检查 kubectl 子命令规则
        if sub_cmd in KUBECTL_SUBCOMMAND_RULES:
            rule = KUBECTL_SUBCOMMAND_RULES[sub_cmd]
            if rule is True:
                # 完全禁止的子命令（如 drain）
                return False
            elif isinstance(rule, set) and len(parts) > 2:
                # 部分禁止：检查第三个参数是否在禁止集合中
                target = parts[2].lower()
                if target in rule:
                    return False

        # 检查是否包含 --all / --all-namespaces 的删除操作
        cmd_str = " ".join(parts).lower()
        if sub_cmd == "delete":
            if "--all-namespaces" in cmd_str:
                return False
            if "--all" in parts:
                return False

    return True