from django.urls import path
from .views import MarketListView, OpenPositionsView

urlpatterns = [
    path("market/", MarketListView.as_view(), name="market-list"),
    path("positions/", OpenPositionsView.as_view(), name="open-positions"),
]
