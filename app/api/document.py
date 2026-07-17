import os


from fastapi import (

    APIRouter,

    UploadFile,

    File,

    Form

)


from app.services.document_service import (

    DocumentService

)



router = APIRouter(

    prefix="/document",

    tags=["document"]

)



UPLOAD_DIR = "./data/uploads"



os.makedirs(

    UPLOAD_DIR,

    exist_ok=True

)



@router.post("/upload")
async def upload_document(

    owner: str = Form(...),

    file: UploadFile = File(...)

):

    # 创建Service（此时Neo4j已经初始化完成）
    service = DocumentService()

    # =====================
    # 保存文件
    # =====================

    file_path = os.path.join(

        UPLOAD_DIR,

        file.filename

    )

    with open(file_path, "wb") as f:

        content = await file.read()

        f.write(content)

    # =====================
    # 解析 + Memory
    # =====================

    result = await service.ingest(

        owner=owner,

        file_path=file_path

    )

    return result



@router.post("/upload")
async def upload_document(

    owner:str = Form(...),

    file:UploadFile = File(...)

):


    # =====================
    # 保存文件
    # =====================


    file_path = os.path.join(

        UPLOAD_DIR,

        file.filename

    )



    with open(

        file_path,

        "wb"

    ) as f:


        content = await file.read()


        f.write(content)



    # =====================
    # 解析 + Memory
    # =====================


    result = await service.ingest(

        owner=owner,

        file_path=file_path

    )


    return result