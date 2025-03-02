import os
# pylint: disable=C0413
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "be_game.settings")

from django.core.asgi import get_asgi_application
# pylint: disable=C0413
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter, ChannelNameRouter
from channels.security.websocket import AllowedHostsOriginValidator

from pong.routing import websocket_urlpatterns as PongUrlPattern
from pong import consumers as PongConsumers

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        URLRouter(PongUrlPattern)
    ),
    "channel": ChannelNameRouter({
        'pong-serverlogic': PongConsumers.PongServerLogicConsumer.as_asgi()
    })
})
