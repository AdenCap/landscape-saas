from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class CanonicalHostRedirectMiddleware:
    """Keep production traffic on one origin so cookies and CSRF stay aligned."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        canonical_host = getattr(settings, "CANONICAL_HOST", "").strip().lower()
        redirect_hosts = {host.lower() for host in getattr(settings, "CANONICAL_REDIRECT_HOSTS", [])}
        current_host = request.get_host().split(":", 1)[0].lower()
        if canonical_host and current_host in redirect_hosts and current_host != canonical_host:
            absolute = request.build_absolute_uri()
            parts = urlsplit(absolute)
            scheme = "https" if not settings.DEBUG else parts.scheme
            return HttpResponsePermanentRedirect(
                urlunsplit((scheme, canonical_host, parts.path, parts.query, parts.fragment))
            )
        return self.get_response(request)
