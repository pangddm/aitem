import asyncio
from app.tools.pod_tools import list_pods

result = asyncio.run(
    list_pods("default")
)

print(result)