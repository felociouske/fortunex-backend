from django.urls import path
from .views import AffiliateOverviewView

urlpatterns = [
    path("overview/", AffiliateOverviewView.as_view(), name="affiliate-overview"),
]
