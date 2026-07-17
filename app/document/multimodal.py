import os
import base64

from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()


client = OpenAI(

    api_key=os.getenv(
        "DASHSCOPE_API_KEY"
    ),

    base_url=
    "https://ws-desdcuc07ogrkiwd.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"

)



def image_understanding(
        image_path:str,
        prompt:str
):


    with open(
        image_path,
        "rb"
    ) as f:

        image_base64 = base64.b64encode(
            f.read()
        ).decode()



    response = client.chat.completions.create(

        model="qwen3.5-397b-a17b",

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