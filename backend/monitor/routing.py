from django.urls import path

from .consumers import AircraftConsumer

websocket_urlpatterns = [
    path("ws/aircraft/", AircraftConsumer.as_asgi()),
]
