from decimal import Decimal

from django.db.models import Sum
from rest_framework import serializers
from .models import Deposit, Withdrawal, PaymentAgent
from .mpesa_service import normalize_phone
import re


class DepositSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deposit
        fields = ["id", "amount", "currency", "created_at", "status"]
        read_only_fields = ["id", "created_at", "status"]


class ManualMpesaDepositSerializer(serializers.Serializer):
    """
    For a user who paid via the Paybill directly (not through the
    app's STK push) and is submitting proof for admin review.
    """
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=1)
    phone_number = serializers.CharField(max_length=20)
    mpesa_code = serializers.CharField(max_length=20)

    def validate_phone_number(self, value):
        normalized = normalize_phone(value)
        if not normalized:
            raise serializers.ValidationError(
                "Enter a valid Safaricom number, e.g. 0712345678 or 254712345678."
            )
        return normalized

    def validate_mpesa_code(self, value):
        # M-Pesa confirmation codes are alphanumeric, ~10 characters (e.g.
        # "QGH7K9L2M1") -- normalize case/whitespace since users often
        # copy-paste them with inconsistent formatting from the SMS.
        code = value.strip().upper().replace(" ", "")
        if not re.fullmatch(r"[A-Z0-9]{6,15}", code):
            raise serializers.ValidationError(
                "Enter a valid M-Pesa confirmation code (letters and numbers only)."
            )
        # Global uniqueness check -- a real M-Pesa code can only ever
        # belong to one transaction, so if it's already attached to a
        # Deposit (by anyone), this submission is either a duplicate or
        # an attempted reuse.
        if Deposit.objects.filter(mpesa_receipt_number=code).exists():
            raise serializers.ValidationError("This M-Pesa code has already been submitted.")
        return code

class WithdrawalSerializer(serializers.ModelSerializer):
    # Overridden to be required + non-blank for new submissions, even
    # though the model field itself is blank=True (that's only to keep
    # old pre-existing rows valid).
    payout_details = serializers.CharField(required=True, allow_blank=False, max_length=255)

    class Meta:
        model = Withdrawal
        fields = ["id", "amount", "currency", "source_wallet", "payout_details", "created_at", "status"]
        read_only_fields = ["id", "created_at", "status"]

    def validate(self, data):
            request = self.context.get("request")
            if request is None:
                return data

            if not request.user.is_kyc_verified:
                raise serializers.ValidationError(
                    "Your account must complete KYC verification before you can withdraw funds."
                )

            wallet = getattr(request.user, "wallet", None)
            source = data.get("source_wallet", Withdrawal.SOURCE_REAL)
            available = getattr(wallet, source, 0) if wallet else 0

            # The balance stored on the wallet is only ever debited when an
            # admin *approves* a withdrawal (see cashier/admin.py) -- a
            # PENDING request doesn't touch it yet. Without this, the same
            # balance could back several simultaneous withdrawal requests:
            # each one would individually validate fine against the
            # untouched wallet balance, only for admin approval to silently
            # reject all but the first. Subtracting this user's other
            # already-pending requests for the same wallet closes that gap
            # and gives an honest error up front instead.
            pending_amount = Withdrawal.objects.filter(
                user=request.user,
                status=Withdrawal.STATUS_PENDING,
                source_wallet=source,
            ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

            available = available - pending_amount

            if available < data["amount"]:
                raise serializers.ValidationError(
                    f"Your requested amount is larger than your available {source.replace('_', ' ')}."
                )
            return data


class StkPushSerializer(serializers.Serializer):
    """Validates the M-Pesa STK Push request payload."""
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=1)
    phone_number = serializers.CharField(max_length=20)

    def validate_phone_number(self, value):
        normalized = normalize_phone(value)
        if not normalized:
            raise serializers.ValidationError(
                "Enter a valid Safaricom number, e.g. 0712345678 or 254712345678."
            )
        return normalized


class PaymentAgentSerializer(serializers.ModelSerializer):
    """Only name and phone number are ever exposed here -- every other
    trust detail shown on the P2P tab lives in the frontend instead, so
    this never needs to change if that content does."""
    class Meta:
        model = PaymentAgent
        fields = ["id", "name", "phone_number"]