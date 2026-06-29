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


class ReferredUserSerializer(serializers.Serializer):
    """
    One row in the referrer's "my referrals" list. `status` is purely
    KYC-status-derived per product decision: a referred user is
    "active" once their KYC is verified, "dormant" otherwise -- nothing
    else (login activity, deposits, etc.) factors in.
    """
    id = serializers.IntegerField()
    email = serializers.EmailField()
    full_name = serializers.CharField()
    joined_at = serializers.DateTimeField(source="date_joined")
    status = serializers.SerializerMethodField()

    def get_status(self, obj):
        return "active" if obj.is_kyc_verified else "dormant"