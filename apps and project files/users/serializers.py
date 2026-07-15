"""
Serializers for the users/auth app.
- UserSerializer         : full profile — read and partial update
- RegisterSerializer      : signup
- LoginSerializer          : login
- WalletSerializer         : read wallet balances
- ChangePasswordSerializer : authenticated password change
- KYCIdentitySerializer / KYCAddressSerializer : per-category KYC submission
"""
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, Wallet, KYCSubmission


class WalletSerializer(serializers.ModelSerializer):
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
            "date_of_birth", "country", "phone_number", "location", "kra_pin",
            "kyc_status", "referral_code",
            "date_joined", "wallet",
        ]
        read_only_fields = [
            "id", "email", "kyc_status", "referral_code", "date_joined", "wallet"
        ]


class RegisterSerializer(serializers.Serializer):
    first_name      = serializers.CharField(max_length=50)
    last_name       = serializers.CharField(max_length=50)
    email           = serializers.EmailField()
    password        = serializers.CharField(min_length=8, write_only=True)
    date_of_birth   = serializers.DateField()
    country         = serializers.CharField(max_length=100, default="Kenya")
    referral_code   = serializers.CharField(max_length=12, required=False, allow_blank=True)

    def validate_email(self, value):
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value.lower()

    def validate_referral_code(self, value):
        if value and not User.objects.filter(referral_code=value).exists():
            raise serializers.ValidationError("Invalid referral code.")
        return value

    def create(self, validated_data):
        referral_code = validated_data.pop("referral_code", "")
        referred_by = User.objects.filter(referral_code=referral_code).first() if referral_code else None

        user = User.objects.create_user(
            username=validated_data["email"].split("@")[0] + "_" + get_random_username_suffix(),
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            date_of_birth=validated_data["date_of_birth"],
            country=validated_data.get("country", "Kenya"),
            referred_by=referred_by,
        )
        return user


def get_random_username_suffix():
    from django.utils.crypto import get_random_string
    return get_random_string(6)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data["email"].lower(), password=data["password"])
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("This account has been deactivated.")
        data["user"] = user
        return data


class ChangePasswordSerializer(serializers.Serializer):
    """
    Requires the CURRENT password to prove it's really the account owner
    (not just someone with a still-valid access token on a stolen
    device), then runs Django's configured AUTH_PASSWORD_VALIDATORS
    against the new one.
    """
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value):
        try:
            validate_password(value, user=self.context["request"].user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def save(self):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


# ── KYC ────────────────────────────────────────────────────────────────────

def _max_5mb(file):
    if file.size > 5 * 1024 * 1024:
        raise serializers.ValidationError("File must be under 5 MB.")
    allowed_types = ["image/jpeg", "image/png", "image/jpg"]
    content_type = getattr(file, "content_type", None)
    if content_type and content_type in allowed_types:
        return
    name = getattr(file, "name", "") or ""
    ext = name.split(".")[-1].lower() if "." in name else ""
    if ext not in ("jpg", "jpeg", "png"):
        raise serializers.ValidationError("Only JPG or PNG images are accepted.")


class KYCIdentitySerializer(serializers.Serializer):
    """
    National ID and Driver's License need both sides; Passport only has
    a single bio-page image. validate() enforces that per document_type
    since front_image/back_image can't carry per-type "required" rules
    on their own.
    """
    document_type = serializers.ChoiceField(choices=KYCSubmission.DOCUMENT_TYPE_CHOICES)
    front_image = serializers.ImageField()
    back_image = serializers.ImageField(required=False)

    def validate_front_image(self, value):
        _max_5mb(value)
        return value

    def validate_back_image(self, value):
        _max_5mb(value)
        return value

    def validate(self, data):
        needs_back = data["document_type"] in (KYCSubmission.DOC_NATIONAL_ID, KYCSubmission.DOC_DRIVERS_LICENSE)
        if needs_back and not data.get("back_image"):
            raise serializers.ValidationError(
                {"back_image": "Both sides are required for this document type."}
            )
        return data

    def save(self, *, user):
        submission, _ = KYCSubmission.objects.update_or_create(
            user=user, category=KYCSubmission.CATEGORY_IDENTITY,
            defaults={
                "document_type": self.validated_data["document_type"],
                "front_image": self.validated_data["front_image"],
                "back_image": self.validated_data.get("back_image"),
                "status": KYCSubmission.STATUS_SUBMITTED,
                "submitted_at": timezone.now(),
                "reviewed_at": None,
            },
        )
        return submission


class KYCAddressSerializer(serializers.Serializer):
    """
    One image (receipt OR a location photo -- user's choice) plus GPS
    coordinates the frontend captured via the browser's Geolocation API.
    """
    address_image = serializers.ImageField()
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)

    def validate_address_image(self, value):
        _max_5mb(value)
        return value

    def save(self, *, user):
        submission, _ = KYCSubmission.objects.update_or_create(
            user=user, category=KYCSubmission.CATEGORY_ADDRESS,
            defaults={
                "address_image": self.validated_data["address_image"],
                "latitude": self.validated_data["latitude"],
                "longitude": self.validated_data["longitude"],
                "status": KYCSubmission.STATUS_SUBMITTED,
                "submitted_at": timezone.now(),
                "reviewed_at": None,
            },
        )
        return submission


class KYCSubmissionReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCSubmission
        fields = [
            "category", "status", "document_type",
            "front_image", "back_image", "address_image",
            "latitude", "longitude", "submitted_at", "reviewed_at", "review_notes",
        ]