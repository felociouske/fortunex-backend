"""
Root URL configuration for Fortunex backend.
All API endpoints are prefixed with /api/v1/
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # Django admin panel (for KYC review, user management, etc.)
    path("admin/", admin.site.urls),

    # Auth endpoints
    path("api/v1/auth/", include("users.urls")),

    # JWT token refresh (used by axios interceptor)
    path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),

    # Wallet endpoints
    path("api/v1/wallet/", include("users.wallet_urls")),

    # Trading endpoints
    path("api/v1/trading/", include("trading.urls")),

    # Bot catalog endpoints
    path("api/v1/bots/", include("bots.urls")),

    # Marketplace endpoints
    path("api/v1/market/", include("market.urls")),

    # Cashier endpoints
    path("api/v1/cashier/", include("cashier.urls")),

    # Affiliate endpoints
    path("api/v1/affiliate/", include("affiliate.urls")),

    # Affiliate endpoints
    path("api/v1/affiliate/", include("affiliate.urls")),

    # Notification endpoints
    path("api/v1/notifications/", include("notifications.urls")),
]

# Serve media files in development (KYC documents, etc.)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
