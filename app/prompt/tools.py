TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "通过 SSH 执行 kubectl 命令",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "需要执行的 kubectl 命令"
                    }
                },
                "required": ["command"]
            }
        }
    }
]