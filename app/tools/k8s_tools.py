"""
结构化 K8s 工具集
提供比原始 kubectl 命令更结构化的操作接口
每个工具返回结构化的 JSON 结果，方便前端展示
"""

import json
import re
from typing import Optional

from app.tools.ssh_client import execute_command


def _parse_table_output(output: str) -> list[dict]:
    """
    解析 kubectl 表格输出为结构化列表
    例如：
    NAME  READY  STATUS  RESTARTS  AGE
    nginx  1/1   Running  0        5m
    →
    [{"NAME": "nginx", "READY": "1/1", "STATUS": "Running", "RESTARTS": "0", "AGE": "5m"}]
    """
    lines = output.strip().split("\n")
    if len(lines) < 2:
        return []

    # 第一行是表头
    headers = lines[0].split()
    result = []
    for line in lines[1:]:
        if not line.strip():
            continue
        values = line.split()
        row = {}
        for i, header in enumerate(headers):
            if i < len(values):
                row[header] = values[i]
            else:
                row[header] = ""
        result.append(row)
    return result


async def kubectl_get_pods(
    namespace: str = "default",
    all_namespaces: bool = False,
    host: str = None, port: int = None,
    username: str = None, password: str = None,
) -> dict:
    """获取 Pod 列表（结构化）"""
    if all_namespaces:
        cmd = "kubectl get pods --all-namespaces"
    else:
        cmd = f"kubectl get pods -n {namespace}"

    try:
        output = execute_command(cmd, host=host, port=port, username=username, password=password)
        pods = _parse_table_output(output)
        return {
            "success": True,
            "command": cmd,
            "pods": pods,
            "count": len(pods),
            "raw": output[:2000],
        }
    except Exception as e:
        return {"success": False, "command": cmd, "error": str(e), "pods": [], "count": 0}


async def kubectl_get_deployments(
    namespace: str = "default",
    all_namespaces: bool = False,
    host: str = None, port: int = None,
    username: str = None, password: str = None,
) -> dict:
    """获取 Deployment 列表（结构化）"""
    if all_namespaces:
        cmd = "kubectl get deployments --all-namespaces"
    else:
        cmd = f"kubectl get deployments -n {namespace}"

    try:
        output = execute_command(cmd, host=host, port=port, username=username, password=password)
        deployments = _parse_table_output(output)
        return {
            "success": True,
            "command": cmd,
            "deployments": deployments,
            "count": len(deployments),
            "raw": output[:2000],
        }
    except Exception as e:
        return {"success": False, "command": cmd, "error": str(e), "deployments": [], "count": 0}


async def kubectl_get_services(
    namespace: str = "default",
    all_namespaces: bool = False,
    host: str = None, port: int = None,
    username: str = None, password: str = None,
) -> dict:
    """获取 Service 列表（结构化）"""
    if all_namespaces:
        cmd = "kubectl get services --all-namespaces"
    else:
        cmd = f"kubectl get services -n {namespace}"

    try:
        output = execute_command(cmd, host=host, port=port, username=username, password=password)
        services = _parse_table_output(output)
        return {
            "success": True,
            "command": cmd,
            "services": services,
            "count": len(services),
            "raw": output[:2000],
        }
    except Exception as e:
        return {"success": False, "command": cmd, "error": str(e), "services": [], "count": 0}


async def kubectl_get_nodes(
    host: str = None, port: int = None,
    username: str = None, password: str = None,
) -> dict:
    """获取 Node 列表（结构化）"""
    cmd = "kubectl get nodes -o wide"

    try:
        output = execute_command(cmd, host=host, port=port, username=username, password=password)
        nodes = _parse_table_output(output)
        return {
            "success": True,
            "command": cmd,
            "nodes": nodes,
            "count": len(nodes),
            "raw": output[:2000],
        }
    except Exception as e:
        return {"success": False, "command": cmd, "error": str(e), "nodes": [], "count": 0}


async def kubectl_get_events(
    namespace: str = "default",
    all_namespaces: bool = False,
    host: str = None, port: int = None,
    username: str = None, password: str = None,
) -> dict:
    """获取 Events（结构化）"""
    if all_namespaces:
        cmd = "kubectl get events --all-namespaces --sort-by='.lastTimestamp'"
    else:
        cmd = f"kubectl get events -n {namespace} --sort-by='.lastTimestamp'"

    try:
        output = execute_command(cmd, host=host, port=port, username=username, password=password)
        events = _parse_table_output(output)
        # 只返回最近 20 条
        return {
            "success": True,
            "command": cmd,
            "events": events[-20:] if len(events) > 20 else events,
            "count": len(events),
            "raw": output[:2000],
        }
    except Exception as e:
        return {"success": False, "command": cmd, "error": str(e), "events": [], "count": 0}


async def kubectl_describe(
    resource_type: str,
    resource_name: str,
    namespace: str = "default",
    host: str = None, port: int = None,
    username: str = None, password: str = None,
) -> dict:
    """Describe 资源（结构化摘要）"""
    cmd = f"kubectl describe {resource_type} {resource_name} -n {namespace}"

    try:
        output = execute_command(cmd, host=host, port=port, username=username, password=password)

        # 提取关键信息
        info = {
            "name": resource_name,
            "namespace": namespace,
            "type": resource_type,
        }

        # 提取状态
        status_match = re.search(r"Status:\s*(\S+)", output)
        if status_match:
            info["status"] = status_match.group(1)

        # 提取 IP
        ip_match = re.search(r"IP:\s*(\S+)", output)
        if ip_match:
            info["ip"] = ip_match.group(1)

        # 提取 Node
        node_match = re.search(r"Node:\s*(\S+)", output)
        if node_match:
            info["node"] = node_match.group(1)

        # 提取 Events 中的 Warning
        warnings = []
        for line in output.split("\n"):
            if "Warning" in line:
                warnings.append(line.strip())

        return {
            "success": True,
            "command": cmd,
            "info": info,
            "warnings": warnings[:10],
            "raw": output[:3000],
        }
    except Exception as e:
        return {"success": False, "command": cmd, "error": str(e), "info": {}, "warnings": []}


async def kubectl_logs(
    resource_name: str,
    namespace: str = "default",
    tail: int = 100,
    previous: bool = False,
    host: str = None, port: int = None,
    username: str = None, password: str = None,
) -> dict:
    """获取 Pod 日志"""
    cmd = f"kubectl logs {resource_name} -n {namespace} --tail={tail}"
    if previous:
        cmd += " --previous"

    try:
        output = execute_command(cmd, host=host, port=port, username=username, password=password)

        # 分析日志中的错误
        error_lines = []
        for line in output.split("\n"):
            lower = line.lower()
            if any(kw in lower for kw in ("error", "exception", "failed", "panic", "fatal", "traceback")):
                error_lines.append(line.strip())

        return {
            "success": True,
            "command": cmd,
            "logs": output[:5000],
            "error_count": len(error_lines),
            "error_lines": error_lines[:20],
            "total_lines": len(output.split("\n")),
        }
    except Exception as e:
        return {"success": False, "command": cmd, "error": str(e), "logs": "", "error_count": 0, "error_lines": []}


async def kubectl_top_pods(
    namespace: str = "default",
    all_namespaces: bool = False,
    host: str = None, port: int = None,
    username: str = None, password: str = None,
) -> dict:
    """获取 Pod 资源使用情况"""
    if all_namespaces:
        cmd = "kubectl top pods --all-namespaces"
    else:
        cmd = f"kubectl top pods -n {namespace}"

    try:
        output = execute_command(cmd, host=host, port=port, username=username, password=password)
        pods = _parse_table_output(output)
        return {
            "success": True,
            "command": cmd,
            "pods": pods,
            "count": len(pods),
            "raw": output[:2000],
        }
    except Exception as e:
        return {"success": False, "command": cmd, "error": str(e), "pods": [], "count": 0}


async def kubectl_top_nodes(
    host: str = None, port: int = None,
    username: str = None, password: str = None,
) -> dict:
    """获取 Node 资源使用情况"""
    cmd = "kubectl top nodes"

    try:
        output = execute_command(cmd, host=host, port=port, username=username, password=password)
        nodes = _parse_table_output(output)
        return {
            "success": True,
            "command": cmd,
            "nodes": nodes,
            "count": len(nodes),
            "raw": output[:2000],
        }
    except Exception as e:
        return {"success": False, "command": cmd, "error": str(e), "nodes": [], "count": 0}


# 工具注册表
K8S_TOOLS = {
    "kubectl_get_pods": kubectl_get_pods,
    "kubectl_get_deployments": kubectl_get_deployments,
    "kubectl_get_services": kubectl_get_services,
    "kubectl_get_nodes": kubectl_get_nodes,
    "kubectl_get_events": kubectl_get_events,
    "kubectl_describe": kubectl_describe,
    "kubectl_logs": kubectl_logs,
    "kubectl_top_pods": kubectl_top_pods,
    "kubectl_top_nodes": kubectl_top_nodes,
}