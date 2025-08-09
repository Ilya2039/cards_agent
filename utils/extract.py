# utils/extract.py

from docx import Document

def extract_text_from_docx(file_path: str) -> str:
    doc = Document(file_path)
    text = "\n".join(para.text.strip() for para in doc.paragraphs if para.text.strip())
    return text