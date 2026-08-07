import paramiko
import threading
import time
from app.core.config import (
    TARGET_HOST,
    TARGET_PORT,
    TARGET_USERNAME,
    TARGET_PASSWORD,
    SSH_TIMEOUT,
    SSH_POOL_MAX_IDLE,
    SSH_POOL_CLEAN_INTERVAL,
)

HOST = TARGET_HOST
PORT = TARGET_PORT
USERNAME = TARGET_USERNAME
PASSWORD = TARGET_PASSWORD

# SSH 连接池（按主机:端口:用户名 缓存连接）
_ssh_pool = {}
_pool_lock = threading.Lock()
POOL_MAX_IDLE = SSH_POOL_MAX_IDLE  # 连接空闲秒数
POOL_CLEAN_INTERVAL = SSH_POOL_CLEAN_INTERVAL  # 每 N 秒清理一次


def _pool_key(host, port, username):
    return f"{host}:{port}:{username}"


def _get_cached_ssh(host, port, username, password, timeout):
    """从连接池获取或创建 SSH 连接"""
    key = _pool_key(host, port, username)
    now = time.time()

    with _pool_lock:
        if key in _ssh_pool:
            entry = _ssh_pool[key]
            # 检查连接是否仍然活跃
            try:
                transport = entry["ssh"].get_transport()
                if transport and transport.is_active():
                    entry["last_used"] = now
                    return entry["ssh"]
            except Exception:
                pass
            # 连接已失效，关闭并移除
            try:
                entry["ssh"].close()
            except Exception:
                pass
            del _ssh_pool[key]

    # 创建新连接
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        host, port, username, password,
        timeout=timeout, banner_timeout=timeout, auth_timeout=timeout,
    )

    with _pool_lock:
        _ssh_pool[key] = {"ssh": ssh, "last_used": now}

    return ssh


def _clean_idle_connections():
    """清理空闲连接（后台定期执行）"""
    now = time.time()
    with _pool_lock:
        expired = [
            k for k, v in _ssh_pool.items()
            if now - v["last_used"] > POOL_MAX_IDLE
        ]
        for k in expired:
            try:
                _ssh_pool[k]["ssh"].close()
            except Exception:
                pass
            del _ssh_pool[k]


# 启动后台清理线程
_cleaner_started = False
_cleaner_lock = threading.Lock()


def _start_cleaner():
    global _cleaner_started
    with _cleaner_lock:
        if _cleaner_started:
            return
        _cleaner_started = True

    def _clean_loop():
        while True:
            time.sleep(POOL_CLEAN_INTERVAL)
            try:
                _clean_idle_connections()
            except Exception:
                pass

    t = threading.Thread(target=_clean_loop, daemon=True)
    t.start()


_start_cleaner()


def execute_command(command: str, host: str = None, port: int = None, username: str = None, password: str = None, _retried: bool = False):
    """在目标主机上执行命令。

    说明：仅对【建立连接/取连接】阶段失败自动重试一次（此时命令尚未下发，可安全重试）；
    连接成功后的真正执行阶段不做重试，避免 kubectl delete/apply 等写操作被重复下发。
    """
    timeout = SSH_TIMEOUT

    _host = host or HOST
    _port = port or PORT
    _username = username or USERNAME
    _password = password or PASSWORD

    def _drop():
        key = _pool_key(_host, _port, _username)
        with _pool_lock:
            if key in _ssh_pool:
                try:
                    _ssh_pool[key]["ssh"].close()
                except Exception:
                    pass
                del _ssh_pool[key]

    # 阶段一：建立/获取连接（失败可安全重试一次）
    ssh = None
    try:
        ssh = _get_cached_ssh(_host, _port, _username, _password, timeout)
    except Exception as e:
        try:
            _drop()
        except Exception:
            pass
        if not _retried:
            time.sleep(1)
            return execute_command(
                command, host=host, port=port, username=username, password=password, _retried=True
            )
        raise RuntimeError(f"SSH 执行失败: {str(e)}")

    # 阶段二：真正执行命令（连接已建立，不再重试）
    try:
        stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
        result = stdout.read().decode()
        error = stderr.read().decode()
        if error:
            return f"STDERR: {error}\nSTDOUT: {result}" if result else error
        return result
    except Exception as e:
        try:
            _drop()
        except Exception:
            pass
        raise RuntimeError(f"SSH 执行失败: {str(e)}")
