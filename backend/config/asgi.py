import os
import sys

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Inicializa Django antes de importar nada que dependa de los modelos.
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402
from django.conf import settings  # noqa: E402

from monitor.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)

# El monitor arranca solo dentro del servidor daphne (no en tests ni en
# comandos de manage.py), en el mismo proceso y event loop que la web.
if settings.MONITOR_ENABLED and os.path.basename(sys.argv[0]) == "daphne":
    from monitor.service import start_with_daphne

    start_with_daphne()
