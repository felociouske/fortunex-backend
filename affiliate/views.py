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
        referred_users = request.user.referrals.all().order_by("-date_joined")

        return Response({
            "link": ReferralLinkSerializer(link).data,
            "commissions": ReferralCommissionSerializer(commissions, many=True).data,
            "referred_users": ReferredUserSerializer(referred_users, many=True).data,
        })