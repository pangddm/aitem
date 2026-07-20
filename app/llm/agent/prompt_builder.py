from app.prompt.sys import SYSTEM_PROMPT


class PromptBuilder:

    def build(
        self,
        knowledge: str,
    ):

        system_prompt = SYSTEM_PROMPT

        if knowledge:

            system_prompt += f"""

以下历史案例仅供参考：

{knowledge}

规则：

1、优先相信 Tool

2、不要照搬历史回答

3、如果案例相似，可借鉴解决思路

"""

        return system_prompt