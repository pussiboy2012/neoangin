import pdfkit
from io import BytesIO

# опции можно настроить
PDFKIT_OPTIONS = {
    "page-size": "A4",
    "encoding": "UTF-8",
    "margin-top": "10mm",
    "margin-bottom": "10mm",
    "margin-left": "10mm",
    "margin-right": "10mm",
    "enable-local-file-access": None  # если подключаешь локальные css/картинки
}

def html_to_pdf_bytes(html: str) -> BytesIO:
    """
    Возвращает BytesIO с pdf.
    """
    pdf_bytes = pdfkit.from_string(html, False, options=PDFKIT_OPTIONS)
    return BytesIO(pdf_bytes)
