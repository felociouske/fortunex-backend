"""
Users app — API views.

POST /auth/register/        → create account
POST /auth/login/           → get JWT tokens
POST /auth/logout/          → blacklist refresh token
POST /auth/token/refresh/   → get new access token
GET  /auth/profile/         → get current user profile
PATCH /auth/profile/        → update profile
POST /auth/kyc/             → submit KYC document
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .models import User
from .serializers import (
    RegisterSerializer, LoginSerializer,
    UserSerializer, KYCSerializer, WalletSerializer,
)


class RegisterView(APIView):
    """
    POST /auth/register/
    Creates a new user account + wallet.
    Returns JWT tokens so the user is logged in immediately.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()

        # Auto-login: generate tokens right after registration
        refresh = RefreshToken.for_user(user)
        return Response({
            "user":    UserSerializer(user).data,
            "access":  str(refresh.access_token),
            "refresh": str(refresh),
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """
    POST /auth/login/
    Accepts email + password, returns access + refresh tokens.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        return Response({
            "user":    UserSerializer(data["user"]).data,
            "access":  data["access"],
            "refresh": data["refresh"],
        }, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """
    POST /auth/logout/
    Blacklists the refresh token so it can no longer be used.
    Requires a logged-in user (valid access token).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"detail": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()   # adds to the simplejwt blacklist table
        except TokenError:
            return Response({"detail": "Token is invalid or already expired."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Logged out successfully."}, status=status.HTTP_205_RESET_CONTENT)


class ProfileView(APIView):
    """
    GET  /auth/profile/  → return full user profile including wallet
    PATCH /auth/profile/ → update allowed fields (name, phone, country)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        # partial=True allows updating only the supplied fields
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)


class KYCView(APIView):
    """
    POST /auth/kyc/
    Upload a government ID or passport for KYC verification.
    Sets kyc_status to SUBMITTED — admin reviews via Django admin panel.
    Requires authenticated user who has not yet submitted KYC.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        # Prevent re-submission if already verified
        if user.kyc_status == "VERIFIED":
            return Response(
                {"detail": "Your KYC is already verified."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = KYCSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        updated_user = serializer.save(user=user)
        return Response({
            "detail": "KYC document submitted successfully. We'll review it within 24 hours.",
            "kyc_status": updated_user.kyc_status,
        }, status=status.HTTP_200_OK)


class WalletView(APIView):
    """
    GET /wallet/balance/
    Returns the three wallet balances for the authenticated user.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # wallet is auto-created on registration (OneToOne)
        try:
            wallet = request.user.wallet
        except Exception:
            return Response({"detail": "Wallet not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = WalletSerializer(wallet)
        return Response(serializer.data)
