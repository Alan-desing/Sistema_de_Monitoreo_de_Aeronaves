import asyncio

from django.core.management.base import BaseCommand, CommandError

from configuration.models import SystemConfig
from monitor.telegram import TelegramError, send_test_message


class Command(BaseCommand):
    help = "Envía un mensaje de prueba (con mapa) al grupo de Telegram con la configuración guardada."

    def handle(self, *args, **options):
        try:
            title, with_map = asyncio.run(send_test_message(SystemConfig.load()))
        except TelegramError as exc:
            raise CommandError(str(exc)) from None
        suffix = "con el mapa" if with_map else "SIN mapa (no se pudo armar la imagen; ver el aviso de arriba)"
        self.stdout.write(self.style.SUCCESS(f"Mensaje de prueba enviado al grupo «{title}» {suffix}."))
