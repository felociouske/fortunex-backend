from django.urls import path
from .views import (
    MarketListView,
    OpenPositionsView,
    PositionHistoryView,
    OpenContractView,
    InstrumentTicksView,
    MyTierView,
    StartBotRunView,
    StopBotRunView,
    MyBotRunView,
)

urlpatterns = [
    path("market/", MarketListView.as_view(), name="market-list"),
    path("instruments/<str:symbol>/ticks/", InstrumentTicksView.as_view(), name="instrument-ticks"),
    path("positions/", OpenPositionsView.as_view(), name="open-positions"),
    path("positions/history/", PositionHistoryView.as_view(), name="position-history"),
    path("contracts/", OpenContractView.as_view(), name="open-contract"),
    path("my-tier/", MyTierView.as_view(), name="my-tier"),
    path("botrun/start/", StartBotRunView.as_view(), name="botrun-start"),
    path("botrun/stop/", StopBotRunView.as_view(), name="botrun-stop"),
    path("botrun/mine/", MyBotRunView.as_view(), name="botrun-mine"),
]