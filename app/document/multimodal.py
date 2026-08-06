import base64

from openai import OpenAI
from app.core.config import DASHSCOPE_API_KEY, VISION_MODEL, VISION_BASE_URL


client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url=VISION_BASE_URL,
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