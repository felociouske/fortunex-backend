from django.urls import path
from .views import DepositView, WithdrawalView

urlpatterns = [
    path("deposit/", DepositView.as_view(), name="cashier-deposit"),
    path("withdrawal/", WithdrawalView.as_view(), name="cashier-withdrawal"),
]
