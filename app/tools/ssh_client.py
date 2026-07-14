import paramiko
import os
from dotenv import load_dotenv
load_dotenv()
HOST = os.getenv("TARGET_HOST")
PORT = int(os.getenv("TARGET_PORT"))
USERNAME = os.getenv("TARGET_USERNAME")
PASSWORD = os.getenv("TARGET_PASSWORD")

def execute_command(command: str):

    ssh = paramiko.SSHClient()

    ssh.set_missing_host_key_policy(
        paramiko.AutoAddPolicy()
    )

    ssh.connect(
        HOST,
        PORT,
        USERNAME,
        PASSWORD
    )

    stdin, stdout, stderr = ssh.exec_command(command)

    result = stdout.read().decode()
    error = stderr.read().decode()

    ssh.close()

    if error:
        return error

    return result