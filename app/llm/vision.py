import base64

from openai import OpenAI
from app.core.config import (
    DASHSCOPE_API_KEY,
    VISION_MODEL,
    VISION_FALLBACK_MODEL,
    VISION_BASE_URL,
)
from app.core.retry import retry_sync


vision_client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url=VISION_BASE_URL,
)



def encode_image(

    image_path:str

):

    with open(

        image_path,

        "rb"

    ) as f:

        image_data=f.read()


    return base64.b64encode(

        image_data

    ).decode(
        "utf-8"
    )





def _vision_models():
    """主模型 + 备用模型（去重），主模型失败时自动切换。"""
    models = [VISION_MODEL]
    if VISION_FALLBACK_MODEL and VISION_FALLBACK_MODEL != VISION_MODEL:
        models.append(VISION_FALLBACK_MODEL)
    return models


def analyze_image(

    image_path:str,

    prompt:str=None

):


    if prompt is None:

        prompt="""

请分析这张图片。

要求：

1. 描述图片整体内容

2. 如果是架构图：
   提取组件名称和连接关系

3. 如果是流程图：
   描述流程步骤

4. 如果是代码截图：
   提取代码内容

5. 如果是表格：
   提取关键字段

输出结构化中文描述。

"""


    image_base64 = encode_image(

        image_path

    )


    last_exc = None
    for model in _vision_models():
        try:
            response = retry_sync(
                lambda: vision_client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{image_base64}"
                                    },
                                },
                            ],
                        }
                    ],
                )
            )
            return response.choices[0].message.content
        except Exception as e:
            last_exc = e
            print(
                f"[Vision] 模型 {model} 调用失败: "
                f"{type(e).__name__}: {e}"
            )
            continue
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("全部视觉模型调用失败")
