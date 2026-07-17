import os
import uuid

from docx import Document

from app.document.extractors.image import parse_image



IMAGE_DIR = "./data/document_images"


os.makedirs(
    IMAGE_DIR,
    exist_ok=True
)



def extract_docx_images(doc):


    images=[]


    for rel in doc.part.rels.values():


        if "image" not in rel.target_ref:

            continue



        image_part = rel.target_part


        ext = ".png"


        image_name = (

            str(uuid.uuid4())

            +

            ext

        )


        image_path = os.path.join(

            IMAGE_DIR,

            image_name

        )


        with open(

            image_path,

            "wb"

        ) as f:

            f.write(

                image_part.blob

            )


        images.append(

            image_path

        )


    return images





def parse_docx(

    file_path:str

):


    doc = Document(

        file_path

    )


    chunks=[]



    # =====================
    # 1. 提取文字
    # =====================


    for paragraph in doc.paragraphs:


        text = paragraph.text.strip()



        if not text:

            continue



        chunks.append(

            {

                "type":"text",

                "content":text,

                "source":file_path,

                "metadata":{

                    "file_type":"docx"

                }

            }

        )




    # =====================
    # 2. 提取图片
    # =====================


    image_paths = extract_docx_images(

        doc

    )



    for image_path in image_paths:


        image_result = parse_image(

            image_path

        )


        chunks.append(

            {

                "type":"image",

                "content":
                image_result["content"],

                "source":file_path,

                "metadata":{

                    "image_path":image_path,

                    "file_type":"docx"

                }

            }

        )



    return chunks