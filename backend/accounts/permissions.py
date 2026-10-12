from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import BasePermission

from .roles import is_admin


class SessionAuthentication401(SessionAuthentication):
    """Igual que la de DRF, pero sin sesión responde 401 en lugar de 403.

    Así el frontend distingue "sesión vencida" (401) de "sin permiso" (403).
    """

    def authenticate_header(self, request):
        return "Session"


class IsAdmin(BasePermission):
    message = "Solo un administrador puede hacer esto."

    def has_permission(self, request, view):
        return is_admin(request.user)
