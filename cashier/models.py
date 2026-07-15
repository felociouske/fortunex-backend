from django.db import models
from django.conf import settings


class Deposit(models.Model):
    STATUS_PENDING    = "PENDING"     # manual deposit, awaiting admin review
    STATUS_PROCESSING = "PROCESSING"  # M-Pesa STK push sent, waiting on the user's PIN + Safaricom's callback
    STATUS_APPROVED   = "APPROVED"
    STATUS_REJECTED   = "REJECTED"    # manual deposit, an admin said no
    STATUS_FAILED     = "FAILED"      # M-Pesa payment failed/cancelled/timed out -- a SYSTEM outcome, no admin involved
    STATUS_CHOICES = [
        (STATUS_PENDING,    "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_APPROVED,   "Approved"),
        (STATUS_REJECTED,   "Rejected"),
        (STATUS_FAILED,     "Failed"),
    ]

    METHOD_MANUAL = "MANUAL"
    METHOD_MPESA  = "MPESA"
    METHOD_MANUAL_MPESA = "MANUAL_MPESA"  # user paid via Paybill directly, submitted the code themselves
    METHOD_BLUEPAY = "BLUEPAY"            # M-Pesa STK push routed through BluePay, separate rail from Daraja above
    METHOD_CHOICES = [
        (METHOD_MANUAL, "Manual"),
        (METHOD_MPESA,  "M-Pesa (automatic)"),
        (METHOD_MANUAL_MPESA, "M-Pesa (manual, user-submitted code)"),
        (METHOD_BLUEPAY, "M-Pesa via BluePay"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="deposits")
    amount = models.DecimalField(max_digits=18, decimal_places=2)   # always USD -- the wallet's own currency
    currency = models.CharField(max_length=5, default="USD")
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING)

    # ── M-Pesa-specific fields (left blank/null for MANUAL deposits) ─────────
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default=METHOD_MANUAL)
    phone_number = models.CharField(max_length=15, blank=True, help_text="MSISDN in 2547XXXXXXXX format")
    kes_amount = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True,
        help_text="Actual KES amount sent to Daraja (amount * exchange_rate at request time)",
    )
    exchange_rate = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        help_text="USD->KES rate used at request time, kept for audit trail",
    )
    merchant_request_id = models.CharField(max_length=100, blank=True)
    # null=True + default=None (NOT "") so multiple manual deposits can all
    # have "no checkout id" without colliding on the unique constraint --
    # SQL allows many NULLs under UNIQUE, but not many empty strings.
    checkout_request_id = models.CharField(max_length=100, unique=True, null=True, blank=True, default=None)
    mpesa_receipt_number = models.CharField(max_length=50, blank=True)
    result_code = models.IntegerField(null=True, blank=True)
    result_desc = models.CharField(max_length=255, blank=True)
    callback_received_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Deposit {self.amount} {self.currency} for {self.user.email} [{self.status}]"


class Withdrawal(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    # Withdrawals only ever come from real_balance (trade earnings) or
    # yield_balance (referral commissions) -- never deposit_balance,
    # since that's reserved for buying bots/AIs.
    SOURCE_REAL = "real_balance"
    SOURCE_YIELD = "yield_balance"
    SOURCE_CHOICES = [
        (SOURCE_REAL, "Real balance (trade earnings)"),
        (SOURCE_YIELD, "Yield balance (referral commissions)"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="withdrawals")
    payout_details = models.CharField(max_length=255, blank=True, help_text="Phone number, bank account, or other payout destination")
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=5, default="USD")
    source_wallet = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_REAL)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING)

    def __str__(self):
        return f"Withdrawal {self.amount} {self.currency} for {self.user.email} [{self.status}]"


class PaymentAgent(models.Model):
    """
    A trusted individual/business users can send M-Pesa payments to
    directly (P2P deposits), then submit the resulting code on the
    M-Pesa (manual) tab for the usual admin review.

    Deliberately minimal: only what actually needs to live in a
    database and be updatable without a code change. Everything
    trust-related (star rating, description, badges) is intentionally
    NOT here, it lives in the frontend instead, per product decision.
    """
    name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20, help_text="Shown to users exactly as entered, e.g. 0712345678")
    is_active = models.BooleanField(default=True, help_text="Uncheck to hide from the app without deleting the record")
    display_order = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first in the list")

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return f"{self.name} ({self.phone_number})"

class PaymentSettings(models.Model):
    """
    Singleton config for the manual M-Pesa Paybill instructions shown
    on the deposit form (see ExchangeRateView). Admin edits the one row
    here instead of these values being fixed in settings.py/.env, so
    they can change without a redeploy.
    """
    paybill_number = models.CharField(max_length=20, default="174379")
    account_name = models.CharField(
        max_length=50, default="FortuneX",
        help_text="Shown as the Account Number step in payment instructions, a shared brand name, not a per-user reference",
    )

    def save(self, *args, **kwargs):
        self.pk = 1  # enforce a single row, always overwrite the same one
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # block deletion, this config should always exist once created

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Paybill {self.paybill_number} / {self.account_name}"