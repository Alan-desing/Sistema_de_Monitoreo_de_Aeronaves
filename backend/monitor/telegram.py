"""Envío de alertas a un grupo de Telegram (Bot API).

Cada alerta se envía como foto (mapa con la zona y la aeronave, ver
``mapimage``) con el texto como leyenda. Si el mapa no se puede armar o
Telegram rechaza la foto, se envía solo el texto: la alerta nunca se pierde
por culpa de la imagen.

El token del bot forma parte de la URL, así que nunca se incluye en los
mensajes de error ni en el log.
"""

import asyncio
import logging
import time

import httpx
from django.conf import settings

from .alerts import format_alert_message
from .mapimage import demo_position, render_alert_map
from .zone import Zone

logger = logging.getLogger(__name__)

API_URL = "https://api.telegram.org"
REQUEST_TIMEOUT_S = 10.0
PHOTO_TIMEOUT_S = 30.0
MAP_TIMEOUT_S = 20.0
CAPTION_MAX = 1024  # límite de Telegram para la leyenda de una foto
MAX_ATTEMPTS = 4
QUEUE_SIZE = 100
# Telegram admite unos 20 mensajes por minuto en un mismo grupo.
MIN_GAP_S = 3.0


class TelegramError(Exception):
    def __init__(self, message, *, status=None, retryable=False, retry_after=None, migrate_to=None):
        super().__init__(message)
        self.status = status
        self.retryable = retryable
        self.retry_after = retry_after
        self.migrate_to = migrate_to


async def _call(client, token, method, *, timeout=REQUEST_TIMEOUT_S, **request):
    url = f"{API_URL}/bot{token}/{method}"
    try:
        response = await client.post(url, timeout=timeout, **request)
    except httpx.HTTPError as exc:
        # Sin ``from exc``: la excepción original contiene la URL con el token.
        raise TelegramError(f"Error de red con Telegram ({exc.__class__.__name__}).", retryable=True) from None

    try:
        data = response.json()
    except ValueError:
        data = {}
    if response.status_code == 200 and data.get("ok"):
        return data.get("result")

    status = response.status_code
    params = data.get("parameters") or {}
    description = data.get("description") or f"HTTP {status}"
    raise TelegramError(
        f"Telegram rechazó el mensaje: {description}",
        status=status,
        retryable=status == 429 or status >= 500,
        retry_after=params.get("retry_after"),
        migrate_to=params.get("migrate_to_chat_id"),
    )


async def send_message(client, token, chat_id, text):
    return await _call(client, token, "sendMessage",
                       json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True})


async def send_photo(client, token, chat_id, photo, caption):
    return await _call(client, token, "sendPhoto", timeout=PHOTO_TIMEOUT_S,
                       data={"chat_id": chat_id, "caption": caption},
                       files={"photo": ("mapa.jpg", photo, "image/jpeg")})


async def send_alert(client, token, chat_id, text, photo=None):
    """Foto con leyenda si hay mapa; si Telegram rechaza la foto, solo texto."""
    if photo and len(text) <= CAPTION_MAX:
        try:
            return await send_photo(client, token, chat_id, photo, text)
        except TelegramError as exc:
            # 400 por la imagen (no por el chat): reintentar sin foto. Los
            # errores de red, 429, 5xx o de chat/token se propagan.
            if exc.status != 400 or exc.migrate_to:
                raise
            logger.warning("Telegram rechazó la imagen del mapa (%s); se envía solo el texto.", exc)
    return await send_message(client, token, chat_id, text)


def tiles_client():
    return httpx.AsyncClient(headers={"User-Agent": settings.ADSBFI_USER_AGENT}, follow_redirects=False)


async def build_map(render, alert, zone):
    """Imagen del mapa o None. Nunca lanza: sin mapa, la alerta sale como texto."""
    if render is None or zone is None:
        return None
    try:
        return await asyncio.wait_for(render(alert, zone), MAP_TIMEOUT_S)
    except Exception as exc:  # noqa: BLE001 — la imagen es opcional
        logger.warning("No se pudo armar el mapa de la alerta de %s (%s); se envía solo el texto.",
                       alert.get("label"), exc or exc.__class__.__name__)
        return None


def demo_alert(config):
    zone = Zone.from_config(config)
    lat, lon = demo_position(zone)
    return {
        "hex": "e0b390", "label": "DEMO123", "flight": "DEMO123", "registration": "LV-XXX", "type": "C172",
        "alt_ft": 2500, "alt_m": 762, "gs": 95, "track": 270, "true_heading": None,
        "dst": zone.radius_nm * 0.55, "lat": lat, "lon": lon, "zone": zone.name, "time": time.time(),
    }


async def send_test_message(config):
    """Envía un mensaje de prueba (con mapa) con la configuración dada.

    Devuelve ``(título del grupo, si incluyó el mapa)``. Lanza
    ``TelegramError`` con un mensaje explicativo para el usuario si falla.
    """
    if not config.telegram_enabled:
        raise TelegramError("Telegram no está configurado (falta el token del bot o el chat id del grupo).")
    alert = demo_alert(config)
    text = "🧪 MENSAJE DE PRUEBA — no es una alerta real\n\n" + format_alert_message(alert)
    async with tiles_client() as tiles:
        photo = await build_map(lambda a, z: render_alert_map(a, z, client=tiles), alert, Zone.from_config(config))
    async with httpx.AsyncClient() as client:
        try:
            result = await send_alert(client, config.telegram_bot_token, config.telegram_chat_id, text, photo)
        except TelegramError as exc:
            raise TelegramError(explain(exc), status=exc.status) from None
    title = ((result or {}).get("chat") or {}).get("title") or config.telegram_chat_id
    return title, bool(photo) and "photo" in (result or {})


def explain(exc):
    if exc.migrate_to:
        return (f"{exc} — el grupo pasó a ser supergrupo; cambiar el chat id a {exc.migrate_to} "
                "en Configuración.")
    if exc.status == 401:
        return f"{exc} — el token del bot no es válido."
    if exc.status in (400, 403):
        return f"{exc} — revisar el chat id y que el bot sea miembro del grupo."
    return str(exc)


class TelegramNotifier:
    """Cola de alertas con un único worker: el monitor nunca espera a Telegram.

    En cada intento lee la configuración guardada, así un token o chat id
    corregido desde la web se usa en el próximo envío.
    """

    def __init__(self, load_config, *, client=None, render_map=None, min_gap_s=MIN_GAP_S, sleep=asyncio.sleep):
        self._load_config = load_config
        self._client = client
        self._render_map = render_map  # None: se usa render_alert_map con su propio cliente
        self._min_gap_s = min_gap_s
        self._sleep = sleep
        self._queue = None
        self._task = None

    def start(self):
        if self._task is None:
            self._queue = self._queue or asyncio.Queue(maxsize=QUEUE_SIZE)
            self._task = asyncio.get_running_loop().create_task(self._worker(), name="telegram-notifier")

    def enqueue(self, alert, zone=None):
        if self._queue is None:
            self._queue = asyncio.Queue(maxsize=QUEUE_SIZE)
        try:
            self._queue.put_nowait((alert, zone))
        except asyncio.QueueFull:
            logger.error("Cola de Telegram llena: no se enviará la alerta de %s.", alert["label"])

    async def _worker(self):
        client = self._client or httpx.AsyncClient()
        tiles = tiles_client()
        render = self._render_map or (lambda alert, zone: render_alert_map(alert, zone, client=tiles))
        try:
            while True:
                alert, zone = await self._queue.get()
                try:
                    await self.deliver(client, alert, zone, render=render)
                except Exception:
                    logger.exception("Error inesperado enviando la alerta de %s a Telegram.", alert["label"])
                finally:
                    self._queue.task_done()
                await self._sleep(self._min_gap_s)
        finally:
            await tiles.aclose()
            if self._client is None:
                await client.aclose()

    async def deliver(self, client, alert, zone=None, *, render=None):
        """Envía una alerta con reintentos. Devuelve True si se envió."""
        config = await self._load_config()
        if not config.telegram_enabled:
            logger.info("Telegram no está configurado: la alerta de %s no se envía por Telegram.", alert["label"])
            return False
        text = format_alert_message(alert)
        photo = await build_map(render or self._render_map, alert, zone)
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if attempt > 1:
                config = await self._load_config()
                if not config.telegram_enabled:
                    logger.info("Telegram se desactivó: la alerta de %s no se envía.", alert["label"])
                    return False
            try:
                await send_alert(client, config.telegram_bot_token, config.telegram_chat_id, text, photo)
                logger.info("Alerta de %s enviada a Telegram%s.", alert["label"], " con mapa" if photo else "")
                return True
            except TelegramError as exc:
                if not exc.retryable:
                    logger.error("No se pudo enviar la alerta de %s: %s", alert["label"], explain(exc))
                    return False
                if attempt == MAX_ATTEMPTS:
                    break
                wait = exc.retry_after or 5 * 2 ** (attempt - 1)
                logger.warning("Falló el envío a Telegram (%s, intento %d/%d). Reintento en %s s.",
                               exc, attempt, MAX_ATTEMPTS, wait)
                await self._sleep(wait)
        logger.error("No se pudo enviar la alerta de %s a Telegram tras %d intentos.", alert["label"], MAX_ATTEMPTS)
        return False
