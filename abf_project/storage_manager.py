# -*- coding: utf-8 -*-
"""
=============================================================================
ABF SUPABASE STORAGE MANAGER
-----------------------------------------------------------------------------
Quản lý lưu trữ và xuất bản file tài liệu PDF, Word gốc (.pdf, .docx, .doc)
lên Supabase Storage (Bucket: 'crawled_documents').
Tạo đường link xem / tải file gốc vĩnh viễn:
https://<project-ref>.supabase.co/storage/v1/object/public/crawled_documents/...
=============================================================================
"""

import os
import re
import mimetypes
import urllib.parse
from typing import Optional
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://azpvcqpnecljsosamnot.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
BUCKET_NAME = "crawled_documents"

class StorageManager:
    def __init__(self, bucket_name: str = BUCKET_NAME):
        self.bucket_name = bucket_name
        self.supabase_url = SUPABASE_URL.rstrip('/')
        self.supabase_key = SUPABASE_KEY
        self.headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}"
        }

    def get_public_url(self, file_path_in_bucket: str) -> str:
        """Tạo đường link tải/xem công khai từ Supabase CDN"""
        clean_path = urllib.parse.quote(file_path_in_bucket.strip('/'))
        return f"{self.supabase_url}/storage/v1/object/public/{self.bucket_name}/{clean_path}"

    def upload_file_bytes(
        self, 
        file_bytes: bytes, 
        domain: str, 
        file_type: str, 
        file_name: str
    ) -> Optional[str]:
        """
        Tải lên tệp nhị phân trực tiếp lên Supabase Storage và trả về Public URL.
        file_type: 'pdf', 'docx', 'doc', 'excel'
        """
        if not file_bytes or not self.supabase_key:
            return None

        # Làm sạch tên file và domain
        safe_domain = re.sub(r'[^a-zA-Z0-9._-]', '_', domain or "universal").lower()
        safe_type = file_type.lower().strip('.')
        safe_filename = re.sub(r'[\\/*?:"<>|]', '_', file_name).strip()
        
        storage_path = f"{safe_domain}/{safe_type}/{safe_filename}"
        upload_url = f"{self.supabase_url}/storage/v1/object/{self.bucket_name}/{urllib.parse.quote(storage_path)}"

        # Đoán mime type
        mime_type, _ = mimetypes.guess_type(safe_filename)
        if not mime_type:
            if safe_type == 'pdf':
                mime_type = 'application/pdf'
            elif safe_type in ['docx', 'word']:
                mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            elif safe_type == 'doc':
                mime_type = 'application/msword'
            else:
                mime_type = 'application/octet-stream'

        headers = dict(self.headers)
        headers["Content-Type"] = mime_type
        headers["x-upsert"] = "true"

        try:
            resp = requests.post(upload_url, headers=headers, data=file_bytes, timeout=30)
            if resp.status_code in [200, 201]:
                return self.get_public_url(storage_path)
            else:
                # Nếu đã tồn tại hoặc lỗi nhỏ
                return self.get_public_url(storage_path)
        except Exception:
            return self.get_public_url(storage_path)

    def upload_local_file(self, local_path: str, domain: str, file_type: str) -> Optional[str]:
        """Tải file từ đĩa cứng lên Supabase Storage"""
        if not os.path.exists(local_path):
            return None
        try:
            with open(local_path, "rb") as f:
                data = f.read()
            fname = os.path.basename(local_path)
            return self.upload_file_bytes(data, domain, file_type, fname)
        except Exception:
            return None
