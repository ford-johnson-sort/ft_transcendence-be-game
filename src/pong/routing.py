# chat/routing.py
from django.urls import re_path
from .consumers import PongGameConsumer

websocket_urlpatterns = [
    re_path(r'^game/ws/pong/(?P<room_uuid>[0-9a-f-]+)/(?P<user>\w+)$', PongGameConsumer.as_asgi()),
]
