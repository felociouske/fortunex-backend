from rest_framework import serializers
from .models import BotProduct


class BotProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = BotProduct
        fields = ["id", "name", "description", "price", "category", "active"]
