"""
WebSocket consumers for live trading data.

TickConsumer:
    Joins the channel group for one instrument's symbol and relays every
    tick broadcast by the price engine (engine.py) to the connected
    client. Stateless and open to any authenticated user — price data
    isn't sensitive.

PositionConsumer:
    Joins a per-user channel group and relays updates about that user's
    own contracts: opened, live price/P&L ticks while open, and the
    final settled (won/lost) event. Requires authentication — this is
    the user's own trading activity.

BotRunConsumer:
    Joins a per-user channel group and relays bot-automation run status:
    each trade settling within the run, and the final stop event.
    Requires authentication.
"""
import json

from channels.generic.websocket import AsyncJsonWebsocketConsumer


class TickConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.symbol = self.scope["url_route"]["kwargs"]["symbol"]
        self.group_name = f"ticks_{self.symbol}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def tick_message(self, event):
        await self.send_json(event["data"])


class PositionConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.group_name = f"positions_user_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def position_message(self, event):
        await self.send_json(event["data"])


class BotRunConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.group_name = f"botrun_user_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def botrun_message(self, event):
        await self.send_json(event["data"])