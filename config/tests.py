import os
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from config.supabase_storage import SupabaseStorage


class SupabaseStorageTests(SimpleTestCase):
    @override_settings(SITE_URL="https://app.fieldlgx.test")
    @patch.dict(os.environ, {
        "SUPABASE_PROJECT_URL": "https://example.supabase.co",
        "SUPABASE_SERVICE_KEY": "service-role-key",
        "SUPABASE_STORAGE_BUCKET": "uploads",
    })
    def test_url_proxies_existing_public_urls_through_app(self):
        storage = SupabaseStorage()

        url = storage.url("https://example.supabase.co/storage/v1/object/public/uploads/business_logos/logo.png")

        self.assertEqual(url, "https://app.fieldlgx.test/uploads/business_logos/logo.png")

    @patch.dict(os.environ, {
        "SUPABASE_PROJECT_URL": "https://example.supabase.co",
        "SUPABASE_SERVICE_KEY": "service-role-key",
        "SUPABASE_STORAGE_BUCKET": "uploads",
    })
    @patch("config.supabase_storage.requests.get")
    def test_open_downloads_with_service_key_instead_of_public_url(self, mock_get):
        response = Mock()
        response.content = b"image-bytes"
        response.raise_for_status.return_value = None
        mock_get.return_value = response
        storage = SupabaseStorage()

        f = storage.open("business_logos/logo.png")

        self.assertEqual(f.read(), b"image-bytes")
        mock_get.assert_called_once()
        called_url = mock_get.call_args.args[0]
        called_headers = mock_get.call_args.kwargs["headers"]
        self.assertEqual(called_url, "https://example.supabase.co/storage/v1/object/uploads/business_logos/logo.png")
        self.assertEqual(called_headers["Authorization"], "Bearer service-role-key")
