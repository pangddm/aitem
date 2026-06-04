import subprocess

def run_kubectl_command(cmd: str):

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    return result.stdout

