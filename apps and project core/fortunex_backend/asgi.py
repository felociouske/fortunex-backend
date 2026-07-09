"""
ASGI config for fortunex_backend project.

Routes plain HTTP through Django as normal, and routes WebSocket
connections (ws://.../ws/...) through Channels -- used for the live
price feed, live position updates, and live M-Pesa deposit status.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fortunex_backend.settings')

# Must call get_asgi_application() before importing anything that touches
# models, to make sure Django's app registry is populated first.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from .ws_auth import JWTAuthMiddlewareStack  # noqa: E402
from trading.routing import websocket_urlpatterns as trading_ws_urlpatterns  # noqa: E402
from cashier.routing import websocket_urlpatterns as cashier_ws_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddlewareStack(
        URLRouter(trading_ws_urlpatterns + cashier_ws_urlpatterns)
    ),
})