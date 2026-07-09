from channels.generic.websocket import AsyncJsonWebsocketConsumer


class DepositConsumer(AsyncJsonWebsocketConsumer):
    """
    Per-user channel: relays this user's M-Pesa deposit status changes
    (PROCESSING -> APPROVED/FAILED) the instant Daraja's callback lands,
    so the Cashier page shows a live result instead of polling.
    """
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return
        self.group_name = f"deposit_user_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def deposit_message(self, event):
        await self.send_json(event["data"])