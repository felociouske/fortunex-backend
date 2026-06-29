from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AutomationProduct, UserAutomation
from .serializers import (
    AutomationProductSerializer,
    PurchaseAutomationSerializer,
    UserAutomationSerializer,
)
from .services import purchase_automation


class BotCatalogView(APIView):
    """GET /bots/catalog/ -- all active bot tiers."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bots = AutomationProduct.objects.filter(active=True, kind=AutomationProduct.KIND_BOT)
        return Response(AutomationProductSerializer(bots, many=True).data)


class AICatalogView(APIView):
    """GET /bots/ai-catalog/ -- all active AI tiers."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ais = AutomationProduct.objects.filter(active=True, kind=AutomationProduct.KIND_AI)
        return Response(AutomationProductSerializer(ais, many=True).data)


class MyAutomationView(APIView):
    """GET /bots/my-automation/ -- the user's currently active automation, plus full ownership history."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        history = UserAutomation.objects.filter(user=request.user).select_related("product")
        active = history.filter(active=True).first()
        return Response({
            "active": UserAutomationSerializer(active).data if active else None,
            "history": UserAutomationSerializer(history, many=True).data,
        })


class PurchaseAutomationView(APIView):
    """
    POST /bots/purchase/  { "product_id": <id> }
    Buys and activates a bot or AI tier using the user's deposit_balance.
    Deactivates whatever was previously active, and pays a referral
    commission to the buyer's referrer (if any).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PurchaseAutomationSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        product = serializer._product
        try:
            automation = purchase_automation(request.user, product)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(UserAutomationSerializer(automation).data, status=status.HTTP_201_CREATED)