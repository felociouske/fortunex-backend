from django.urls import path
from .views import BotCatalogView

urlpatterns = [
    path("catalog/", BotCatalogView.as_view(), name="bot-catalog"),
]
