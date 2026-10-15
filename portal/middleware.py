from django.core.exceptions import PermissionDenied


class TechnicalAdminOnlyMiddleware:
    """Business roles never acquire technical Admin access through is_staff."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path_info.startswith('/admin/') and request.user.is_authenticated and not request.user.is_superuser:
            raise PermissionDenied
        return self.get_response(request)
