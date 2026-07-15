from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.crypto import get_random_string
from django.conf import settings


def kyc_document_upload_path(instance, filename):
    """
    Kept only so old migrations (0001_initial.py) can still resolve this
    reference when Django loads the full migration history -- the field
    that used this was removed in 0003_kyc_rework.py, but the historical
    migration file that CREATED it still imports this by dotted path.
    Do not delete this until you squash migrations and drop that history.
    """
    return f"kyc/{instance.id}/{filename}"


def kyc_upload_path(instance, filename):
    """Store KYC docs under media/kyc/<user_id>/<category>/filename"""
    return f"kyc/{instance.user_id}/{instance.category.lower()}/{filename}"


class User(AbstractUser):
    """
    Extended user model.
    - Login is via email (not username)
    - Each user gets a unique referral code on registration
    - KYC must be VERIFIED before trading or withdrawals
    """

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

    email = models.EmailField(unique=True)
    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = ["username"]

    # Profile fields
    date_of_birth = models.DateField(null=True, blank=True)
    country       = models.CharField(max_length=100, default="Kenya")
    phone_number  = models.CharField(max_length=20, blank=True)
    # Free-text, user-entered -- distinct from the precise GPS coordinates
    # captured during KYC address verification (that's compliance data,
    # this is just "what shows on your profile").
    location      = models.CharField(max_length=255, blank=True, help_text="e.g. Nairobi, Kenya")
    kra_pin       = models.CharField(max_length=11, blank=True, help_text="Kenya Revenue Authority PIN, e.g. A123456789Z")

    # Overall KYC gate -- unchanged meaning from before: must be VERIFIED
    # to trade/withdraw. Now driven by KYCSubmission rows (see below)
    # instead of a single document field.
    kyc_status = models.CharField(max_length=20, choices=KYC_CHOICES, default=KYC_PENDING)

    # Referral system
    referral_code = models.CharField(max_length=12, unique=True, blank=True)
    referred_by = models.ForeignKey(
        "self", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="referrals",
    )

    def __str__(self):
        return f"{self.email} [{self.kyc_status}]"

    def save(self, *args, **kwargs):
            if not self.referral_code:
                self.referral_code = self._generate_referral_code()
            super().save(*args, **kwargs)
            # Existing users never hit the line above, since their
            # referral_code is never blank on an update save -- old-format
            # codes (e.g. IOVDHZJP) are left exactly as stored.

    def _generate_referral_code(self):
        """
        New-format referral code: 'ft' + 8 random digits (e.g.
        ft78267238). Deliberately NOT based on user id/signup order --
        a sequential code (ft00000001, ft00000002, ...) is guessable
        and lets anyone enumerate every referral code on the platform
        just by counting up. Random digits, collision-checked against
        the DB like the old alnum codes were, close that off.
        """
        while True:
            code = "ft" + get_random_string(length=8, allowed_chars="0123456789")
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


class KYCSubmission(models.Model):
    """
    One row per (user, category) -- resubmitting overwrites the same
    row rather than creating a new one, matching the old model's
    "resubmit" behaviour. Ownership/Income categories exist here for
    forward-compatibility but have no submission endpoint yet (they're
    "Coming soon" in the UI) -- so in practice only IDENTITY and
    ADDRESS rows will exist for a while.
    """
    CATEGORY_IDENTITY  = "IDENTITY"
    CATEGORY_ADDRESS   = "ADDRESS"
    CATEGORY_OWNERSHIP = "OWNERSHIP"
    CATEGORY_INCOME    = "INCOME"
    CATEGORY_CHOICES = [
        (CATEGORY_IDENTITY,  "Proof of Identity"),
        (CATEGORY_ADDRESS,   "Proof of Address"),
        (CATEGORY_OWNERSHIP, "Proof of Ownership"),
        (CATEGORY_INCOME,    "Proof of Income"),
    ]

    STATUS_PENDING   = "PENDING"    # not yet submitted
    STATUS_SUBMITTED = "SUBMITTED"  # awaiting admin review
    STATUS_VERIFIED  = "VERIFIED"
    STATUS_REJECTED  = "REJECTED"
    STATUS_CHOICES = [
        (STATUS_PENDING,   "Pending"),
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_VERIFIED,  "Verified"),
        (STATUS_REJECTED,  "Rejected"),
    ]

    DOC_NATIONAL_ID      = "NATIONAL_ID"
    DOC_PASSPORT         = "PASSPORT"
    DOC_DRIVERS_LICENSE  = "DRIVERS_LICENSE"
    DOCUMENT_TYPE_CHOICES = [
        (DOC_NATIONAL_ID,     "National ID"),
        (DOC_PASSPORT,        "Passport"),
        (DOC_DRIVERS_LICENSE, "Driver's License"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="kyc_submissions")
    category = models.CharField(max_length=12, choices=CATEGORY_CHOICES)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING)

    # ── Identity-only fields ──────────────────────────────────────────────
    # National ID / Driver's License need both sides; Passport only has
    # one bio-page image, so back_image stays blank for that type.
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES, blank=True)
    front_image = models.FileField(upload_to=kyc_upload_path, null=True, blank=True)
    back_image = models.FileField(upload_to=kyc_upload_path, null=True, blank=True)

    # ── Address-only fields ───────────────────────────────────────────────
    # One image (receipt OR a location photo, user's choice) plus GPS
    # coordinates captured automatically via the browser's Geolocation API.
    address_image = models.FileField(upload_to=kyc_upload_path, null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True, help_text="Admin notes on this category's review")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "category"], name="one_submission_per_category")
        ]

    def __str__(self):
        return f"{self.user.email} - {self.get_category_display()} [{self.status}]"