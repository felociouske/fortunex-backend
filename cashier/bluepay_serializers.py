from rest_framework import serializers
from .bluepay_service import normalize_phone


class BluePayStkPushSerializer(serializers.Serializer):
    """Validates the BluePay M-Pesa STK Push request payload."""
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=1)
    phone_number = serializers.CharField(max_length=20)

    def validate_phone_number(self, value):
        normalized = normalize_phone(value)
        if not normalized:
            raise serializers.ValidationError(
                "Enter a valid Safaricom number, e.g. 0712345678 or 254712345678."
            )
        return normalized