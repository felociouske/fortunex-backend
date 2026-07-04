"""
Views for the users/auth app.
"""
from django.contrib.auth import login
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, KYCSubmission
from .serializers import (
    UserSerializer, RegisterSerializer, LoginSerializer, WalletSerializer,
    ChangePasswordSerializer, KYCIdentitySerializer, KYCAddressSerializer,
    KYCSubmissionReadSerializer,
)


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            "user": UserSerializer(user).data,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        return Response({
            "user": UserSerializer(user).data,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            pass
        return Response({"detail": "Logged out."}, status=status.HTTP_200_OK)


class ProfileView(APIView):
    """
    GET  /auth/profile/  → return full user profile including wallet
    PATCH /auth/profile/ → update allowed fields (name, phone, country, location, kra_pin)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)


class ChangePasswordView(APIView):
    """
    POST /auth/change-password/
    Requires old_password + new_password. On success, blacklists every
    outstanding refresh token for this user -- changing your password
    ends every other session, not just this one.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()

        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
        for token in OutstandingToken.objects.filter(user=request.user):
            BlacklistedToken.objects.get_or_create(token=token)

        return Response(
            {"detail": "Password changed successfully. Please log in again."},
            status=status.HTTP_200_OK,
        )


class KYCView(APIView):
    """
    GET  /auth/kyc/  -> status + data for all 4 categories (Ownership/
                         Income come back as a fixed "not available yet"
                         placeholder -- there's no submission for them).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        submissions = {s.category: s for s in request.user.kyc_submissions.all()}

        def category_payload(category):
            sub = submissions.get(category)
            if sub:
                return KYCSubmissionReadSerializer(sub).data
            return {"category": category, "status": "PENDING"}

        return Response({
            "overall_status": request.user.kyc_status,
            "identity": category_payload(KYCSubmission.CATEGORY_IDENTITY),
            "address": category_payload(KYCSubmission.CATEGORY_ADDRESS),
            "ownership": {"category": KYCSubmission.CATEGORY_OWNERSHIP, "status": "SUSPENDED"},
            "income": {"category": KYCSubmission.CATEGORY_INCOME, "status": "SUSPENDED"},
        })


class KYCIdentityView(APIView):
    """POST /auth/kyc/identity/ -- submit Proof of Identity."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.kyc_status == User.KYC_VERIFIED:
            return Response({"detail": "Your KYC is already verified."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = KYCIdentitySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        submission = serializer.save(user=request.user)
        return Response(
            KYCSubmissionReadSerializer(submission).data,
            status=status.HTTP_200_OK,
        )


class KYCAddressView(APIView):
    """POST /auth/kyc/address/ -- submit Proof of Address."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.kyc_status == User.KYC_VERIFIED:
            return Response({"detail": "Your KYC is already verified."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = KYCAddressSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        submission = serializer.save(user=request.user)
        return Response(
            KYCSubmissionReadSerializer(submission).data,
            status=status.HTTP_200_OK,
        )


class WalletView(APIView):
    """
    GET /wallet/balance/
    Returns the three wallet balances for the authenticated user.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            wallet = request.user.wallet
        except Exception:
            return Response({"detail": "Wallet not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(WalletSerializer(wallet).data)