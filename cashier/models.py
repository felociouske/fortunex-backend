from django.db import models
from django.conf import settings


class Deposit(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="deposits")
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=5, default="USD")
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING)

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
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=5, default="USD")
    source_wallet = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_REAL)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING)

    def __str__(self):
        return f"Withdrawal {self.amount} {self.currency} for {self.user.email} [{self.status}]"