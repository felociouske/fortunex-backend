from rest_framework import serializers
from .models import ReferralCommission, ReferralLink


class ReferralLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralLink
        fields = ["code", "created_at"]


class ReferralCommissionSerializer(serializers.ModelSerializer):
    referred_email = serializers.CharField(source="referred.email", read_only=True)

    class Meta:
        model = ReferralCommission
        fields = ["id", "amount", "description", "created_at", "referred_email"]
