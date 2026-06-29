from django.contrib.auth.models import AbstractUser #extends Django built-in User model instead of building one from scratch.
from django.db import models #allows to create database tables using Django models.
from django.utils.crypto import get_random_string

def kyc_document_upload_path(instance, filename): #tells django where to store the uploaded KYC documents from users. 
    """Store KYC docs under media/kyc/<user_id>/filename"""
    return f"kyc/{instance.id}/{filename}"


class User(AbstractUser):
    """
    Extended user model.
    - Login is via email (not username)
    - Each user gets a unique referral code on registration
    - KYC must be VERIFIED before trading or withdrawals
    """

    # KYC status choices
    KYC_PENDING   = "PENDING"
    KYC_SUBMITTED = "SUBMITTED"
    KYC_VERIFIED  = "VERIFIED"
    KYC_REJECTED  = "REJECTED"
    KYC_CHOICES   = [
        (KYC_PENDING,   "Pending"),
        (KYC_SUBMITTED, "Submitted"),
        (KYC_VERIFIED,  "Verified"),
        (KYC_REJECTED,  "Rejected"),
    ]

    # Override email to be unique — used as login identifier
    email = models.EmailField(unique=True)
    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = ["username"]   # username still required for AbstractUser

    # Profile fields
    date_of_birth = models.DateField(null=True, blank=True)
    country       = models.CharField(max_length=100, default="Kenya")
    phone_number  = models.CharField(max_length=20, blank=True)

    # KYC
    kyc_status   = models.CharField(max_length=20, choices=KYC_CHOICES, default=KYC_PENDING)
    kyc_document = models.FileField(
        upload_to=kyc_document_upload_path, null=True, blank=True,
        help_text="Government-issued ID or passport scan"
    )
    kyc_submitted_at = models.DateTimeField(null=True, blank=True)
    kyc_reviewed_at  = models.DateTimeField(null=True, blank=True)
    kyc_notes        = models.TextField(blank=True, help_text="Admin notes on KYC review")

    # Referral system
    referral_code = models.CharField(
        max_length=12, unique=True, blank=True,
    )
    referred_by = models.ForeignKey(
        "self", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="referrals",
    )

    def __str__(self):
        return f"{self.email} [{self.kyc_status}]"

    def save(self, *args, **kwargs):
        # Auto-generate a unique referral code if not set
        if not self.referral_code:
            self.referral_code = self._generate_referral_code()
        super().save(*args, **kwargs)

    def _generate_referral_code(self):
        while True:
            code = get_random_string(
                length=8,
                allowed_chars='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
            )
            if not User.objects.filter(referral_code=code).exists():
                return code

    @property
    def is_kyc_verified(self):
        return self.kyc_status == self.KYC_VERIFIED

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email


class Wallet(models.Model):
    """
    Three-wallet system per user:
    - real_balance    : funds earned from trading
    - deposit_balance : deposited funds (used to buy bots/AIs)
    - yield_balance   : referral commissions earned
    """
    user             = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    real_balance     = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    deposit_balance  = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    yield_balance    = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    currency         = models.CharField(max_length=5, default="USD")
    updated_at       = models.DateTimeField(auto_now=True)

    def __str__(self):
        return (
            f"{self.user.email} | "
            f"Real: {self.real_balance} | "
            f"Deposit: {self.deposit_balance} | "
            f"Yield: {self.yield_balance}"
        )

    @property
    def total_balance(self):
        return self.real_balance + self.deposit_balance + self.yield_balance
