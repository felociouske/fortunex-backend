# Wallet URL patterns.
#
# The Wallet model and WalletView both live inside the `users` app
# (see models.py / views.py) — there is no separate `wallet` app.
# This file exists only to keep the public URL prefix /api/v1/wallet/
# matching what the frontend already expects, without renaming the
# users app or moving the model (which would require a risky migration).
from django.urls import path
from .views import WalletView

urlpatterns = [
    path("balance/", WalletView.as_view(), name="wallet-balance"),
]