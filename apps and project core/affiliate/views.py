from django.db.models import Sum, Value, DecimalField, Q
from django.db.models.functions import Coalesce
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import ReferralCommission, ReferralLink
from .serializers import ReferralCommissionSerializer, ReferralLinkSerializer, ReferredUserSerializer


class AffiliateOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        link, _ = ReferralLink.objects.get_or_create(user=request.user, defaults={"code": request.user.referral_code})
        commissions = ReferralCommission.objects.filter(referrer=request.user)

        # One row per referred user, immediately on sign-up (unchanged from
        # before) -- now also carrying their total commission earned so far,
        # computed here rather than stored, so it's always in sync with the
        # underlying ReferralCommission rows.
        # `referral_source` is ReferralCommission.referred's related_name --
        # i.e. "all commission rows where THIS user is the referred party".
        # Coalesce covers users with zero commission rows (Sum would
        # otherwise return None, not 0).
        referred_users = request.user.referrals.annotate(
            commission_earned=Coalesce(
                Sum("referral_source__amount", filter=Q(referral_source__referrer=request.user)),
                Value(0),
                output_field=DecimalField(max_digits=18, decimal_places=2),
            )
        ).order_by("-date_joined")

        return Response({
            "link": ReferralLinkSerializer(link).data,
            "commissions": ReferralCommissionSerializer(commissions, many=True).data,
            "referred_users": ReferredUserSerializer(referred_users, many=True).data,
        })