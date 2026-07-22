import paramiko
import os
from dotenv import load_dotenv

load_dotenv()
HOST = os.getenv("TARGET_HOST")
PORT = int(os.getenv("TARGET_PORT", 22))
USERNAME = os.getenv("TARGET_USERNAME")
PASSWORD = os.getenv("TARGET_PASSWORD")

def execute_command(command: str):

    ssh = paramiko.SSHClient()

    ssh.set_missing_host_key_policy(
        paramiko.AutoAddPolicy()
    )

    # 增加超时机制，避免无限阻塞
    timeout = int(os.getenv("SSH_TIMEOUT", "30"))  # 默认30秒超时

    try:
        ssh.connect(
            HOST,
            PORT,
            USERNAME,
            PASSWORD,
            timeout=timeout,
            banner_timeout=timeout,
            auth_timeout=timeout,
        )

        stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)

        result = stdout.read().decode()
        error = stderr.read().decode()

        ssh.close()

        if error:
            # 把 stderr 和 stdout 都带上，方便排查
            return f"STDERR: {error}\nSTDOUT: {result}" if result else error

        return result

    except Exception as e:
        try:
            ssh.close()
        except:
            pass
        raise RuntimeError(f"SSH 执行失败: {str(e)}")