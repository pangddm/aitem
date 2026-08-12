import os


from app.document.extractors.docx import parse_docx
from app.document.extractors.image import parse_image
from app.document.extractors.pdf import parse_pdf
from app.document.limits import check_size
from app.document.text_utils import read_text



def route_file(path):


    check_size(path)  # 超大文件守卫

    ext = os.path.splitext(path)[1].lower()



    if ext == ".docx":
        return parse_docx(path)

    elif ext in (".png", ".jpg", ".jpeg"):
        return [parse_image(path)]

    elif ext == ".pdf":
        return parse_pdf(path)

    elif ext in (".txt", ".md", ".log", ".yaml", ".yml", ".json", ".csv", ".xml", ".conf", ".cfg", ".ini", ".sh", ".py", ".js", ".ts", ".html", ".css", ".toml"):
        # 纯文本文件：稳健解码（UTF-8 失败回退 GBK 等）
        content = read_text(path)
        return [{"type": "text", "content": content}]

    else:
        raise ValueError(f"unsupported file:{ext}")
