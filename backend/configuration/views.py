from asgiref.sync import async_to_sync
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdmin
from monitor.broadcast import send_config_sync
from monitor.openair import OpenAirError, decode_openair_bytes, parse_openair
from monitor.service import monitor
from monitor.telegram import TelegramError, send_test_message

from .models import SystemConfig
from .serializers import OpenAirUploadSerializer, SystemConfigSerializer


class ConfigView(APIView):
    """GET / PUT / PATCH de la configuración. Solo administradores."""

    permission_classes = [IsAdmin]

    def get(self, request):
        return Response(SystemConfigSerializer(SystemConfig.load()).data)

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        serializer = SystemConfigSerializer(SystemConfig.load(), data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        config = serializer.save()
        # Los navegadores se actualizan sin recargar y el monitor consulta ya
        # con la zona nueva, sin esperar al próximo ciclo.
        send_config_sync(config)
        monitor.request_refresh()
        return Response(SystemConfigSerializer(config).data)


class OpenAirView(APIView):
    """Lee un archivo OpenAir y devuelve los campos de la zona, SIN guardarlos.

    El frontend los carga en el formulario y el administrador los guarda.
    """

    permission_classes = [IsAdmin]
    parser_classes = [MultiPartParser]

    def post(self, request):
        upload = OpenAirUploadSerializer(data=request.data)
        upload.is_valid(raise_exception=True)
        text = decode_openair_bytes(upload.validated_data["file"].read())
        try:
            zone = parse_openair(text)
        except OpenAirError as exc:
            return Response({"file": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(zone.as_config_fields())


class TelegramTestView(APIView):
    """Envía un mensaje de prueba al grupo con la configuración guardada."""

    permission_classes = [IsAdmin]

    def post(self, request):
        try:
            title, with_map = async_to_sync(send_test_message)(SystemConfig.load())
        except TelegramError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        detail = f"Mensaje de prueba enviado al grupo «{title}»"
        detail += " con el mapa." if with_map else " (sin mapa: no se pudo armar la imagen, ver el log)."
        return Response({"detail": detail, "with_map": with_map})
