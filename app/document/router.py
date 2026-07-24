import os


from app.document.extractors.docx import parse_docx
from app.document.extractors.image import parse_image



def route_file(path):


    ext = os.path.splitext(path)[1].lower()



    if ext == ".docx":
        return parse_docx(path)

    elif ext in (".png", ".jpg", ".jpeg"):
        return [parse_image(path)]

    elif ext in (".txt", ".md", ".log", ".yaml", ".yml", ".json", ".csv", ".xml", ".conf", ".cfg", ".ini", ".sh", ".py", ".js", ".ts", ".html", ".css", ".toml"):
        # 纯文本文件：直接读取内容
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return [{"type": "text", "content": content}]

    else:
        raise ValueError(f"unsupported file:{ext}")
