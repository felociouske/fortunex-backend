from django.urls import path
from .bluepay_views import BluePayStkPushView, BluePayWebhookView, BluePayDepositStatusView

urlpatterns = [
    path("stkpush/", BluePayStkPushView.as_view(), name="cashier-bluepay-stkpush"),
    path("webhook/", BluePayWebhookView.as_view(), name="cashier-bluepay-webhook"),
    path("status/<str:checkout_request_id>/", BluePayDepositStatusView.as_view(), name="cashier-bluepay-status"),
]