"""
Supabase Storage backend for Django file uploads.

Stores uploaded files (logos, photos, receipts) in a Supabase Storage bucket
so they persist across deploys on Render / any ephemeral host.

Requires env vars:
  SUPABASE_PROJECT_URL  — e.g. https://xxxxx.supabase.co
  SUPABASE_SERVICE_KEY  — service_role key (NOT the anon key — needs storage write)

The bucket name defaults to "uploads" and is auto-created if missing.
"""
import os
import uuid
from urllib.parse import urljoin

import requests
from django.core.files.base import ContentFile
from django.core.files.storage import Storage


class SupabaseStorage(Storage):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.project_url = os.environ.get("SUPABASE_PROJECT_URL", "").strip().rstrip("/")
        self.service_key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
        self.bucket = os.environ.get("SUPABASE_STORAGE_BUCKET", "uploads")
        self._base = f"{self.project_url}/storage/v1"
        self._headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
        }
        self._bucket_ensured = False

    def _ensure_bucket(self):
        """Create the bucket if it doesn't exist (runs once per process)."""
        if self._bucket_ensured:
            return
        try:
            resp = requests.post(
                f"{self._base}/bucket",
                json={"id": self.bucket, "name": self.bucket, "public": True},
                headers=self._headers,
                timeout=10,
            )
            # 200 = created, 409 = already exists — both fine
            self._bucket_ensured = True
        except Exception:
            self._bucket_ensured = True  # don't retry every request

    def _save(self, name, content):
        self._ensure_bucket()
        # Add a unique prefix to avoid collisions
        ext = name.rsplit(".", 1)[-1] if "." in name else "bin"
        unique_name = f"{uuid.uuid4().hex[:12]}_{name.replace('/', '_')}"
        content.seek(0)
        data = content.read()

        # Detect content type
        content_type = "application/octet-stream"
        ext_lower = ext.lower()
        if ext_lower in ("jpg", "jpeg"):
            content_type = "image/jpeg"
        elif ext_lower == "png":
            content_type = "image/png"
        elif ext_lower == "gif":
            content_type = "image/gif"
        elif ext_lower == "webp":
            content_type = "image/webp"
        elif ext_lower == "svg":
            content_type = "image/svg+xml"
        elif ext_lower == "pdf":
            content_type = "application/pdf"

        resp = requests.post(
            f"{self._base}/object/{self.bucket}/{unique_name}",
            data=data,
            headers={
                **self._headers,
                "Content-Type": content_type,
                "x-upsert": "true",
            },
            timeout=30,
        )

        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Supabase Storage upload failed ({resp.status_code}): {resp.text[:200]}")

        # Return the public URL as the stored "name"
        public_url = f"{self.project_url}/storage/v1/object/public/{self.bucket}/{unique_name}"
        return public_url

    def url(self, name):
        """Return the URL. If the name is already a full URL, return as-is."""
        if name and name.startswith("http"):
            return name
        if name:
            return f"{self.project_url}/storage/v1/object/public/{self.bucket}/{name}"
        return ""

    def exists(self, name):
        """Check if file exists. Full URLs are assumed to exist."""
        if not name:
            return False
        if name.startswith("http"):
            return True
        try:
            resp = requests.head(self.url(name), timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def delete(self, name):
        """Delete a file from Supabase Storage."""
        if not name:
            return
        # Extract the object path from a full URL
        obj_path = name
        prefix = f"{self.project_url}/storage/v1/object/public/{self.bucket}/"
        if name.startswith(prefix):
            obj_path = name[len(prefix):]

        try:
            requests.delete(
                f"{self._base}/object/{self.bucket}",
                json={"prefixes": [obj_path]},
                headers=self._headers,
                timeout=10,
            )
        except Exception:
            pass

    def _open(self, name, mode="rb"):
        """Download a file from Supabase Storage."""
        url = self.url(name)
        if not url:
            return ContentFile(b"")
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            return ContentFile(resp.content, name=name)
        except Exception:
            return ContentFile(b"")

    def size(self, name):
        return 0

    def listdir(self, path):
        return [], []
