from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from monitor.broadcast import disconnect_user_sync

from .permissions import IsAdmin
from .serializers import LoginSerializer, MeSerializer, UserSerializer


class LoginThrottle(SimpleRateThrottle):
    """Limita los intentos de login por nombre de usuario."""

    scope = "login"

    def get_cache_key(self, request, view):
        username = str(request.data.get("username", "")).strip().lower()
        return self.cache_format % {"scope": self.scope, "ident": username or self.get_ident(request)}


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """Entrega la cookie ``csrftoken`` que el frontend necesita para los POST."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request, **serializer.validated_data)
        if user is None:
            # authenticate() ya rechaza a los usuarios inactivos.
            return Response({"detail": "Usuario o contraseña incorrectos."}, status=status.HTTP_400_BAD_REQUEST)
        login(request, user)
        return Response(MeSerializer(user).data)


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(MeSerializer(request.user).data)


def end_sessions(user):
    """Cierra las sesiones y los WebSocket abiertos de un usuario."""
    for session in Session.objects.filter(expire_date__gt=timezone.now()):
        if session.get_decoded().get("_auth_user_id") == str(user.pk):
            session.delete()
    disconnect_user_sync(user.pk)


class UserViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                  mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Gestión de usuarios (solo administradores). No se borran: se desactivan."""

    permission_classes = [IsAdmin]
    serializer_class = UserSerializer
    queryset = User.objects.order_by("username").prefetch_related("groups")

    def perform_update(self, serializer):
        was_active = serializer.instance.is_active
        password_changed = bool(serializer.validated_data.get("password"))
        user = serializer.save()
        if (was_active and not user.is_active) or password_changed:
            end_sessions(user)
