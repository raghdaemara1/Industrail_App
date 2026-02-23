import os
from config import FILE_STORAGE_BACKEND, FILE_STORAGE_DIR

class FileStore:
    def __init__(self):
        self.backend = FILE_STORAGE_BACKEND
        if self.backend == "local":
            os.makedirs(FILE_STORAGE_DIR, exist_ok=True)

    def save_file(self, md5: str, file_bytes: bytes):
        if self.backend == "local":
            path = os.path.join(FILE_STORAGE_DIR, md5[:2])
            os.makedirs(path, exist_ok=True)
            with open(os.path.join(path, f"{md5}.pdf"), 'wb') as f:
                f.write(file_bytes)
        # azure implementation skipped for demo

    def get_file(self, md5: str) -> bytes:
        if self.backend == "local":
            path = os.path.join(FILE_STORAGE_DIR, md5[:2], f"{md5}.pdf")
            if os.path.exists(path):
                with open(path, 'rb') as f:
                    return f.read()
        return None
