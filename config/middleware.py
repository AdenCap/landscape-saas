from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class CanonicalHostRedirectMiddleware:
    """Keep public and app traffic on the right FIELDLGX origins."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        canonical_host = getattr(settings, "CANONICAL_HOST", "").strip().lower()
        redirect_hosts = {host.lower() for host in getattr(settings, "CANONICAL_REDIRECT_HOSTS", [])}
        current_host = request.get_host().split(":", 1)[0].lower()
        app_host = getattr(settings, "APP_HOST", "").strip().lower()
        app_redirect_hosts = {host.lower() for host in getattr(settings, "APP_REDIRECT_HOSTS", [])}
        app_prefixes = tuple(getattr(settings, "APP_PATH_PREFIXES", ()))
        if (
            app_host
            and current_host in app_redirect_hosts
            and current_host != app_host
            and request.path.startswith(app_prefixes)
        ):
            absolute = request.build_absolute_uri()
            parts = urlsplit(absolute)
            scheme = "https" if not settings.DEBUG else parts.scheme
            return HttpResponsePermanentRedirect(
                urlunsplit((scheme, app_host, parts.path, parts.query, parts.fragment))
            )
        if canonical_host and current_host in redirect_hosts and current_host != canonical_host:
            absolute = request.build_absolute_uri()
            parts = urlsplit(absolute)
            scheme = "https" if not settings.DEBUG else parts.scheme
            return HttpResponsePermanentRedirect(
                urlunsplit((scheme, canonical_host, parts.path, parts.query, parts.fragment))
            )
        return self.get_response(request)
