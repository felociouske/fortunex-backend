from rest_framework import serializers
from .models import Deposit, Withdrawal


class DepositSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deposit
        fields = ["id", "amount", "currency", "created_at", "status"]
        read_only_fields = ["id", "created_at", "status"]


class WithdrawalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Withdrawal
        fields = ["id", "amount", "currency", "source_wallet", "created_at", "status"]
        read_only_fields = ["id", "created_at", "status"]

    def validate(self, data):
            request = self.context.get("request")
            if request is None:
                return data

            if not request.user.is_kyc_verified:
                raise serializers.ValidationError(
                    "Your account must complete KYC verification before you can withdraw funds."
                )

            wallet = getattr(request.user, "wallet", None)
            source = data.get("source_wallet", Withdrawal.SOURCE_REAL)
            available = getattr(wallet, source, 0) if wallet else 0

            if available < data["amount"]:
                raise serializers.ValidationError(
                    f"Insufficient {source.replace('_', ' ')} for this withdrawal request."
                )
            return data