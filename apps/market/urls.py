from django.urls import path
from .views import MarketplaceView

urlpatterns = [
    path("items/", MarketplaceView.as_view(), name="market-items"),
]
