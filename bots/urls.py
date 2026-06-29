from django.urls import path
from .views import BotCatalogView, AICatalogView, MyAutomationView, PurchaseAutomationView

urlpatterns = [
    path("catalog/", BotCatalogView.as_view(), name="bot-catalog"),
    path("ai-catalog/", AICatalogView.as_view(), name="ai-catalog"),
    path("my-automation/", MyAutomationView.as_view(), name="my-automation"),
    path("purchase/", PurchaseAutomationView.as_view(), name="purchase-automation"),
]