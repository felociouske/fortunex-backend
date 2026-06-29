from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import MarketInstrument, TradePosition
from .serializers import MarketInstrumentSerializer, TradePositionSerializer


class MarketListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        instruments = MarketInstrument.objects.filter(active=True)
        serializer = MarketInstrumentSerializer(instruments, many=True)
        return Response(serializer.data)


class OpenPositionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        positions = TradePosition.objects.filter(user=request.user, status="OPEN")
        serializer = TradePositionSerializer(positions, many=True)
        return Response(serializer.data)
