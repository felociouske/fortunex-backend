"""
WebSocket URL routing for the users app.

  ws/users/wallet/  -> the connected user's live wallet balances, auth required
"""
from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"^ws/users/wallet/$", consumers.WalletConsumer.as_asgi()),
]