from django.db import models
from django.conf import settings


class Deposit(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="deposits")
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=5, default="USD")
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=32, default="PENDING")

    def __str__(self):
        return f"Deposit {self.amount} {self.currency} for {self.user.email}"


class Withdrawal(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="withdrawals")
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=5, default="USD")
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=32, default="PENDING")

    def __str__(self):
        return f"Withdrawal {self.amount} {self.currency} for {self.user.email}"
