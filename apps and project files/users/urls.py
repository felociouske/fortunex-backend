from django.urls import path
from .views import (
    RegisterView, LoginView, LogoutView, ProfileView, WalletView, ChangePasswordView,
    KYCView, KYCIdentityView, KYCAddressView,
)

urlpatterns = [
    path("register/",         RegisterView.as_view(),        name="auth-register"),
    path("login/",            LoginView.as_view(),           name="auth-login"),
    path("logout/",           LogoutView.as_view(),          name="auth-logout"),
    path("profile/",          ProfileView.as_view(),         name="auth-profile"),
    path("change-password/",  ChangePasswordView.as_view(),  name="auth-change-password"),

    path("kyc/",              KYCView.as_view(),             name="auth-kyc"),
    path("kyc/identity/",     KYCIdentityView.as_view(),     name="auth-kyc-identity"),
    path("kyc/address/",      KYCAddressView.as_view(),      name="auth-kyc-address"),
]