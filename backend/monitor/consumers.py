from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from configuration.models import SystemConfig

from . import broadcast
from .service import monitor

# Código de cierre propio (rango 4000-4999) para "sin sesión".
CLOSE_UNAUTHENTICATED = 4401


class AircraftConsumer(AsyncJsonWebsocketConsumer):
    """Envía al navegador las aeronaves, las alertas y los cambios de configuración."""

    groups = []

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated or not user.is_active:
            await self.close(code=CLOSE_UNAUTHENTICATED)
            return
        self.user_group = broadcast.user_group(user.pk)
        await self.channel_layer.group_add(broadcast.GROUP, self.channel_name)
        await self.channel_layer.group_add(self.user_group, self.channel_name)
        await self.accept()

        config = await database_sync_to_async(SystemConfig.load)()
        await self.send_json(
            {
                "type": "snapshot",
                "aircraft": monitor.state.payload(),
                "config": broadcast.public_config(config),
                "status": monitor.status,
            }
        )

    async def disconnect(self, code):
        await self.channel_layer.group_discard(broadcast.GROUP, self.channel_name)
        if hasattr(self, "user_group"):
            await self.channel_layer.group_discard(self.user_group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        # El canal es solo de servidor a navegador.
        pass

    async def monitor_event(self, message):
        await self.send_json(message["event"])

    async def session_close(self, message):
        await self.close(code=CLOSE_UNAUTHENTICATED)
