from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import MarketItem
from .serializers import MarketItemSerializer


class MarketplaceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = MarketItem.objects.filter(active=True)
        serializer = MarketItemSerializer(items, many=True)
        return Response(serializer.data)
