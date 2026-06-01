import os
from unittest.mock import Mock, patch

from django.test import Client, RequestFactory, SimpleTestCase, override_settings

from config.middleware import CanonicalHostRedirectMiddleware
from config.supabase_storage import SupabaseStorage


class CanonicalHostRedirectTests(SimpleTestCase):
    @override_settings(
        ALLOWED_HOSTS=["fieldlgx.com", "www.fieldlgx.com", "app.fieldlgx.com"],
        CANONICAL_HOST="fieldlgx.com",
        CANONICAL_REDIRECT_HOSTS=["www.fieldlgx.com"],
        APP_HOST="app.fieldlgx.com",
        APP_REDIRECT_HOSTS=["fieldlgx.com", "www.fieldlgx.com"],
        APP_PATH_PREFIXES=("/accounts/", "/dashboard/", "/billing/"),
        DEBUG=False,
    )
    def test_www_redirects_to_canonical_host(self):
        response = Client().get("/", HTTP_HOST="www.fieldlgx.com", secure=True)

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "https://fieldlgx.com/")

    @override_settings(
        ALLOWED_HOSTS=["fieldlgx.com", "www.fieldlgx.com", "app.fieldlgx.com"],
        CANONICAL_HOST="fieldlgx.com",
        CANONICAL_REDIRECT_HOSTS=["www.fieldlgx.com"],
        APP_HOST="app.fieldlgx.com",
        APP_REDIRECT_HOSTS=["fieldlgx.com", "www.fieldlgx.com"],
        APP_PATH_PREFIXES=("/accounts/", "/dashboard/", "/billing/"),
        DEBUG=False,
    )
    def test_canonical_host_does_not_redirect(self):
        response = Client().get("/", HTTP_HOST="fieldlgx.com", secure=True)

        self.assertNotEqual(response.status_code, 301)

    @override_settings(
        ALLOWED_HOSTS=["fieldlgx.com", "www.fieldlgx.com", "app.fieldlgx.com"],
        CANONICAL_HOST="fieldlgx.com",
        CANONICAL_REDIRECT_HOSTS=["www.fieldlgx.com"],
        APP_HOST="app.fieldlgx.com",
        APP_REDIRECT_HOSTS=["fieldlgx.com", "www.fieldlgx.com"],
        APP_PATH_PREFIXES=("/accounts/", "/dashboard/", "/billing/"),
        DEBUG=False,
    )
    def test_public_app_path_redirects_to_app_subdomain(self):
        response = Client().get("/accounts/login/?next=/dashboard/", HTTP_HOST="fieldlgx.com", secure=True)

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "https://app.fieldlgx.com/accounts/login/?next=/dashboard/")

    @override_settings(
        ALLOWED_HOSTS=["fieldlgx.com", "www.fieldlgx.com", "app.fieldlgx.com"],
        CANONICAL_HOST="fieldlgx.com",
        CANONICAL_REDIRECT_HOSTS=["www.fieldlgx.com"],
        APP_HOST="app.fieldlgx.com",
        APP_REDIRECT_HOSTS=["fieldlgx.com", "www.fieldlgx.com"],
        APP_PATH_PREFIXES=("/accounts/", "/dashboard/", "/billing/"),
        DEBUG=False,
    )
    def test_app_subdomain_does_not_redirect_back_to_public_domain(self):
        request = RequestFactory().get("/accounts/login/", HTTP_HOST="app.fieldlgx.com", secure=True)
        middleware = CanonicalHostRedirectMiddleware(lambda _request: Mock(status_code=200))
        response = middleware(request)

        self.assertEqual(response.status_code, 200)


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
