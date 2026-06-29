"""
Serializers for the users app.
- RegisterSerializer  : validates and creates a new user + wallet
- LoginSerializer     : validates credentials, returns tokens + user data
- UserSerializer      : read/update profile
- KYCSerializer       : document submission
- WalletSerializer    : read wallet balances
"""
from django.contrib.auth import authenticate #used during login to verify email and password.
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, Wallet


class WalletSerializer(serializers.ModelSerializer):
    """Returns the three wallet balances for the current user."""
    class Meta:
        model  = Wallet
        fields = ["real_balance", "deposit_balance", "yield_balance", "currency", "updated_at"]
        read_only_fields = fields


class UserSerializer(serializers.ModelSerializer):
    """Full user profile — read and partial update."""
    wallet = WalletSerializer(read_only=True)

    class Meta:
        model  = User
        fields = [
            "id", "email", "first_name", "last_name", "username",
            "date_of_birth", "country", "phone_number",
            "kyc_status", "referral_code",
            "date_joined", "wallet",
        ]
        read_only_fields = [
            "id", "email", "kyc_status", "referral_code", "date_joined", "wallet"
        ]


class RegisterSerializer(serializers.Serializer):
    """
    Validates registration data, creates User + Wallet,
    and returns JWT tokens.
    """
    first_name      = serializers.CharField(max_length=50)
    last_name       = serializers.CharField(max_length=50)
    email           = serializers.EmailField()
    password        = serializers.CharField(min_length=8, write_only=True)
    date_of_birth   = serializers.DateField()
    country         = serializers.CharField(max_length=100, default="Kenya")
    referral_code   = serializers.CharField(max_length=12, required=False, allow_blank=True)

    def validate_email(self, value):
        """Reject duplicate emails."""
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value.lower()

    def validate_referral_code(self, value):
        """If provided, verify the referral code belongs to a real user."""
        if value:
            if not User.objects.filter(referral_code=value.upper()).exists():
                raise serializers.ValidationError("Invalid referral code.")
        return value.upper() if value else value

    def create(self, validated_data):
        referral_code = validated_data.pop("referral_code", None)

        # Find referrer if code was provided
        referrer = None
        if referral_code:
            try:
                referrer = User.objects.get(referral_code=referral_code)
            except User.DoesNotExist:
                pass

        # Create user — Django hashes the password via set_password internally
        user = User.objects.create_user(
            username      = validated_data["email"],  # use email as username
            email         = validated_data["email"],
            password      = validated_data["password"],
            first_name    = validated_data["first_name"],
            last_name     = validated_data["last_name"],
            date_of_birth = validated_data.get("date_of_birth"),
            country       = validated_data.get("country", "Kenya"),
            referred_by   = referrer,
        )

        # Create the user's 3-wallet system
        Wallet.objects.create(user=user)

        return user


class LoginSerializer(serializers.Serializer):
    """
    Authenticates email + password, returns JWT tokens + user data.
    """
    email    = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email    = data["email"].lower()
        password = data["password"]

        # Django's authenticate uses the custom USERNAME_FIELD (email)
        user = authenticate(request=self.context.get("request"), email=email, password=password)

        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("This account has been disabled.")

        # Generate JWT token pair
        refresh = RefreshToken.for_user(user)
        return {
            "user":    user,
            "access":  str(refresh.access_token),
            "refresh": str(refresh),
        }


class KYCSerializer(serializers.Serializer):
    """
    Accepts a document upload (image or PDF) for KYC verification.
    Sets user's kyc_status to SUBMITTED and records submission timestamp.
    """
    document = serializers.FileField()

    def validate_document(self, file):
        """Only allow images and PDF, max 5 MB. Be defensive when running behind different upload clients."""
        allowed_types = ["image/jpeg", "image/png", "image/jpg", "application/pdf"]
        content_type = getattr(file, 'content_type', None)
        size = getattr(file, 'size', None)

        # Accept when content_type matches known types
        if content_type and content_type in allowed_types:
            pass
        else:
            # Fallback: check filename extension
            name = getattr(file, 'name', '') or ''
            ext = name.split('.')[-1].lower() if '.' in name else ''
            if ext not in ('jpg', 'jpeg', 'png', 'pdf'):
                raise serializers.ValidationError("Only JPG, PNG, or PDF documents are accepted.")

        if size is not None and size > 5 * 1024 * 1024:  # 5 MB limit
            raise serializers.ValidationError("File size must not exceed 5 MB.")
        return file

    def save(self, user):
        file = self.validated_data["document"]
        user.kyc_document    = file
        user.kyc_status      = User.KYC_SUBMITTED
        user.kyc_submitted_at = timezone.now()
        user.save(update_fields=["kyc_document", "kyc_status", "kyc_submitted_at"])
        return user
