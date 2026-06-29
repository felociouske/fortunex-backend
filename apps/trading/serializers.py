from rest_framework import serializers
from .models import MarketInstrument, TradePosition


class MarketInstrumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketInstrument
        fields = ["id", "name", "symbol", "category", "description", "active"]


class TradePositionSerializer(serializers.ModelSerializer):
    instrument = MarketInstrumentSerializer(read_only=True)

    class Meta:
        model = TradePosition
        fields = [
            "id", "instrument", "side", "opened_at", "stake",
            "entry_price", "current_price", "profit_loss", "status",
        ]
