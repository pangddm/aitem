from app.document.parser import parse

from app.memory.container import (
    memory_container
)

from app.memory.classes import (
    MemorySource
)



class DocumentService:


    def __init__(self):

        self.memory_service = (
            memory_container.create_service()
        )



    async def ingest(

        self,

        owner:str,

        file_path:str

    ):


        # =====================
        # 1. 文档解析
        # =====================

        chunks = parse(

            file_path

        )


        if not chunks:

            return {

                "status":"empty",

                "message":
                "no content extracted"

            }



        # =====================
        # 2. 转换Memory输入格式
        # =====================


        messages=[]


        for chunk in chunks:


            messages.append(

                {

                "role":"user",

                "content":
                f"""
            文档来源:
            {file_path}

            内容类型:
            {chunk["type"]}

            内容:
            {chunk["content"]}
            """

                }

            )


        # =====================
        # 3. 写入Memory
        # =====================


        result = await self.memory_service.process(

            owner=owner,

            messages=messages,

            source=MemorySource.DOCUMENT

        )



        return {


            "status":"success",


            "file":file_path,


            "chunks":

            len(chunks),


            "memory":result


        }