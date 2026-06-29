import paramiko

HOST = "192.168.143.13"
PORT = 22
USERNAME = "root"
PASSWORD = "Awcloud!23"

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