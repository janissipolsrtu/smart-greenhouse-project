from urllib.parse import quote

from django.conf import settings
from django.http import HttpResponseRedirect


class RequireLoginMiddleware:
    """Require authentication for web UI pages while keeping API/public auth routes open."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        if request.user.is_authenticated:
            return self.get_response(request)

        if path.startswith('/admin/') or path.startswith('/static/') or path.startswith('/api/'):
            return self.get_response(request)

        if not path.startswith('/smart-greenhouse/'):
            return self.get_response(request)

        public_prefixes = (
            '/smart-greenhouse/login/',
            '/smart-greenhouse/register/',
            '/smart-greenhouse/verify-email/',
            '/smart-greenhouse/api/',
        )
        if any(path.startswith(prefix) for prefix in public_prefixes):
            return self.get_response(request)

        next_url = quote(request.get_full_path(), safe='/?=&')
        login_url = f"{settings.LOGIN_URL}?next={next_url}"
        return HttpResponseRedirect(login_url)
