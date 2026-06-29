from rest_framework import serializers
from .models import MarketItem


class MarketItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketItem
        fields = ["id", "name", "description", "price", "category", "tags", "active"]
