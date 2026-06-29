from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import BotProduct
from .serializers import BotProductSerializer


class BotCatalogView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bots = BotProduct.objects.filter(active=True)
        serializer = BotProductSerializer(bots, many=True)
        return Response(serializer.data)
