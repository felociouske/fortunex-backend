from rest_framework import serializers

from .models import AutomationProduct, UserAutomation


class AutomationProductSerializer(serializers.ModelSerializer):
    win_chance_percent = serializers.SerializerMethodField()

    class Meta:
        model = AutomationProduct
        fields = [
            "id", "name", "description", "kind", "tier", "price",
            "win_chance", "win_chance_percent", "unlocked_contract_count",
            "commission_rate", "active",
        ]

    def get_win_chance_percent(self, obj):
        return float(obj.win_chance) * 100


class UserAutomationSerializer(serializers.ModelSerializer):
    product = AutomationProductSerializer(read_only=True)

    class Meta:
        model = UserAutomation
        fields = ["id", "product", "purchased_at", "deactivated_at", "active"]


class PurchaseAutomationSerializer(serializers.Serializer):
    """Write serializer for POST /bots/purchase/ -- buys (and activates) a bot or AI tier."""
    product_id = serializers.IntegerField()

    def validate_product_id(self, value):
        try:
            product = AutomationProduct.objects.get(id=value, active=True)
        except AutomationProduct.DoesNotExist:
            raise serializers.ValidationError("This product is not available for purchase.")
        self._product = product
        return value

    def validate(self, data):
        request = self.context["request"]
        user = request.user

        wallet = getattr(user, "wallet", None)
        if wallet is None or wallet.deposit_balance < self._product.price:
            raise serializers.ValidationError(
                "Insufficient deposit balance. Bots and AIs can only be purchased "
                "using your deposit balance."
            )
        return data