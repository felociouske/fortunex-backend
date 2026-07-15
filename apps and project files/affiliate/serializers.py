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
    One row in the referrer's "my referrals" table. `commission_earned`
    is an annotated aggregate (see AffiliateOverviewView), not a real
    model field -- DRF's plain Serializer reads it the same way either
    way, via getattr on the queryset row.
    """
    id = serializers.IntegerField()
    email = serializers.EmailField()
    full_name = serializers.CharField()
    phone_number = serializers.CharField()
    joined_at = serializers.DateTimeField(source="date_joined")
    commission_earned = serializers.DecimalField(max_digits=18, decimal_places=2)
    status = serializers.SerializerMethodField()

    def get_status(self, obj):
        return "active" if obj.is_kyc_verified else "dormant"