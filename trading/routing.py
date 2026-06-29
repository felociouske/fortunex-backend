"""
WebSocket URL routing for the trading app.

  ws/trading/ticks/<symbol>/   -> live price ticks for one instrument
  ws/trading/positions/        -> the connected user's own position updates
                                   (opened/updated/settled), auth required
  ws/trading/botrun/           -> the connected user's bot-automation run
                                   status (trade settled / stopped), auth required
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"^ws/trading/ticks/(?P<symbol>[\w.\-]+)/$", consumers.TickConsumer.as_asgi()),
    re_path(r"^ws/trading/positions/$", consumers.PositionConsumer.as_asgi()),
    re_path(r"^ws/trading/botrun/$", consumers.BotRunConsumer.as_asgi()),
]