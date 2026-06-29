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
        fields = ["id", "amount", "currency", "created_at", "status"]
        read_only_fields = ["id", "created_at", "status"]
