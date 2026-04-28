import mimetypes

from django.core.files.storage import default_storage
from django.http import Http404, HttpResponse
from django.views.decorators.http import require_GET


@require_GET
def uploaded_media(request, path):
    """Serve uploaded media through Django storage.

    Supabase Storage is often private in production. This endpoint lets ImageField
    URLs resolve through the app while the storage backend fetches bytes with the
    service key.
    """
    try:
        f = default_storage.open(path, "rb")
        data = f.read()
        f.close()
    except Exception as exc:
        raise Http404("Uploaded file not found") from exc

    if not data:
        raise Http404("Uploaded file not found")

    content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    response = HttpResponse(data, content_type=content_type)
    response["Cache-Control"] = "public, max-age=3600"
    return response
