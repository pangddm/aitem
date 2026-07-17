import os


from app.document.extractors.docx import parse_docx
from app.document.extractors.image import parse_image



def route_file(path):


    ext = os.path.splitext(path)[1].lower()



    if ext == ".docx":

        return parse_docx(path)



    elif ext in [

        ".png",

        ".jpg",

        ".jpeg"

    ]:

        return [

            parse_image(path)

        ]


    else:

        raise ValueError(

            f"unsupported file:{ext}"

        )