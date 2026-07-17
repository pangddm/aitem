import os
import base64

from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()
VISION_MODEL=os.getenv(
    "VISION_MODEL",
    "qwen3.5-397b-a17b"
)


vision_client = OpenAI(

    api_key=os.getenv(
        "DASHSCOPE_API_KEY"
    ),

    base_url=
    "https://ws-desdcuc07ogrkiwd.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"

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


    response = vision_client.chat.completions.create(

        model=VISION_MODEL,


        messages=[

            {

                "role":"user",

                "content":[

                    {

                    "type":"text",

                    "text":prompt

                    },


                    {

                    "type":"image_url",

                    "image_url":{

                        "url":
                        f"data:image/png;base64,{image_base64}"

                    }

                    }

                ]

            }

        ]

    )


    return response.choices[0].message.content