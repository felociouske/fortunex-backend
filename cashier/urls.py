from django.urls import path
from .views import (
    DepositView, WithdrawalView,
    StkPushView, MpesaCallbackView, DepositStatusView, ExchangeRateView, TransactionsView,
)

urlpatterns = [
    path("deposit/", DepositView.as_view(), name="cashier-deposit"),
    path("withdrawal/", WithdrawalView.as_view(), name="cashier-withdrawal"),
    path("transactions/", TransactionsView.as_view(), name="cashier-transactions"),

    path("mpesa/stkpush/", StkPushView.as_view(), name="cashier-mpesa-stkpush"),
    path("mpesa/callback/", MpesaCallbackView.as_view(), name="cashier-mpesa-callback"),
    path("mpesa/status/<str:checkout_request_id>/", DepositStatusView.as_view(), name="cashier-mpesa-status"),
    path("exchange-rate/", ExchangeRateView.as_view(), name="cashier-exchange-rate"),
]