"""
WalletConsumer: per-user channel that relays this user's wallet balances.

Unlike PositionConsumer, the frontend keeps this socket open on EVERY
authenticated page (navbar, Trader's Hub, Cashier), because the balance
is shown everywhere -- not only on the trading terminal.
"""
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .wallet_events import wallet_snapshot


class WalletConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.group_name = f"wallet_user_{user.id}"
        # Join the group BEFORE reading the snapshot so no update can
        # slip through the gap between the two.
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send the current balances immediately. This also repairs any
        # staleness after a dropped connection: every reconnect starts
        # with the truth, so the frontend needs no separate refetch.
        snapshot = await database_sync_to_async(wallet_snapshot)(user.id)
        if snapshot is not None:
            await self.send_json(snapshot)

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def wallet_message(self, event):
        await self.send_json(event["data"])