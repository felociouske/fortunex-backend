"""
WebSocket URL routing for the cashier app.

  ws/cashier/deposits/  -> the connected user's own M-Pesa deposit status
                            updates (PROCESSING -> APPROVED/FAILED), auth required
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"^ws/cashier/deposits/$", consumers.DepositConsumer.as_asgi()),
]