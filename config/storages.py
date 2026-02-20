"""
Custom storage backends. VercelBlobStorage is used when BLOB_READ_WRITE_TOKEN is set (e.g. on Vercel with Blob store "fieldops-blob").
"""
import os
from urllib.parse import urlparse

from django.core.files.base import ContentFile
from django.core.files.storage import Storage


class VercelBlobStorage(Storage):
    """
    Store uploaded files in Vercel Blob (fieldops-blob or any store linked via BLOB_READ_WRITE_TOKEN).
    The token is set automatically when you add the Blob store to your Vercel project.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._token = os.environ.get("BLOB_READ_WRITE_TOKEN", "").strip()

    def _open(self, name, mode="rb"):
        if not name or not name.startswith("http"):
            return ContentFile(b"")
        try:
            import requests
            resp = requests.get(name, timeout=30)
            resp.raise_for_status()
            return ContentFile(resp.content, name=name)
        except Exception:
            return ContentFile(b"")

    def _save(self, name, content):
        try:
            import vercel_blob
        except ImportError:
            raise RuntimeError("Vercel Blob storage requires: pip install vercel_blob")

        if not self._token:
            raise RuntimeError("BLOB_READ_WRITE_TOKEN must be set to use Vercel Blob storage")

        content.seek(0)
        data = content.read()
        opts = {"addRandomSuffix": "true"}
        resp = vercel_blob.put(name, data, opts)
        if resp and isinstance(resp, dict) and resp.get("url"):
            return resp["url"]
        raise RuntimeError("Vercel Blob put() did not return a url")

    def url(self, name):
        if name and name.startswith("http"):
            return name
        return ""

    def exists(self, name):
        return bool(name and name.startswith("http"))

    def delete(self, name):
        if not name or not name.startswith("http"):
            return
        try:
            import vercel_blob
            vercel_blob.delete(name)
        except Exception:
            pass
