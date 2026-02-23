import hashlib
import pdfplumber
from PyPDF2 import PdfReader
import io
import re

class PDFProcessor:
    def __init__(self, file_bytes: bytes):
        self.file_bytes = file_bytes
        self.md5 = hashlib.md5(file_bytes).hexdigest()
        self.text = ""
        self.has_alarms = False
        self.has_parameters = False

    def extract_text(self) -> str:
        # Try pdfplumber first
        try:
            with pdfplumber.open(io.BytesIO(self.file_bytes)) as pdf:
                pages = [page.extract_text() for page in pdf.pages if page.extract_text()]
                self.text = "\n".join(pages)
        except Exception as e:
            print(f"pdfplumber failed: {e}")
            self.text = ""

        # Fallback to PyPDF2
        if not self.text.strip():
            try:
                reader = PdfReader(io.BytesIO(self.file_bytes))
                pages = [page.extract_text() for page in reader.pages if page.extract_text()]
                self.text = "\n".join(pages)
            except Exception as e:
                print(f"PyPDF2 failed: {e}")

        return self.text

    def classify_content(self):
        text_lower = self.text.lower()
        if not text_lower:
            return

        # Simple regex/keyword classification
        alarm_keywords = ["alarm ", "error ", "fault ", "malfunction"]
        param_keywords = ["parameter", "specification", "limit", "tolerance", "technical data", "dimension", "capacity", "force", "weight", "stroke"]

        alarm_count = sum(1 for kw in alarm_keywords if kw in text_lower)
        param_count = sum(1 for kw in param_keywords if kw in text_lower)
        
        alarm_regex = re.search(r'(alarm|error|fault)\s*[:\-]?\s*\d+', text_lower, re.IGNORECASE)
        param_regex = re.search(r'parameter|technical data|specification', text_lower, re.IGNORECASE)
        
        if alarm_count >= 2 or alarm_regex:
            self.has_alarms = True
        
        if param_count >= 2 or param_regex:
            self.has_parameters = True
