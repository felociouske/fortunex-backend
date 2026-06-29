from django.db import models
from django.conf import settings


class Notification(models.Model):
    """
    A single notification shown to one user. All 5 categories share
    this one model -- KYC, deposit, withdrawal, promotional, and
    system notifications all look the same structurally (title,
    message, optional action button, read state); only WHO creates
    them and WHEN differs:

      KYC          -- auto-created at registration, re-surfaced (see
                       KYCStatusView) every login until verified.
      DEPOSIT      -- auto-created when an admin approves/rejects a
                       Deposit (cashier/admin.py).
      WITHDRAWAL   -- auto-created when an admin approves/rejects a
                       Withdrawal, carrying the admin's remark.
      PROMOTIONAL  -- created manually by an admin via Django admin,
                       targeting one user or broadcast to all.
      SYSTEM       -- same as promotional, for rule-violation /
                       platform notices rather than marketing.
    """
    CATEGORY_KYC = "KYC"
    CATEGORY_DEPOSIT = "DEPOSIT"
    CATEGORY_WITHDRAWAL = "WITHDRAWAL"
    CATEGORY_PROMOTIONAL = "PROMOTIONAL"
    CATEGORY_SYSTEM = "SYSTEM"
    CATEGORY_CHOICES = [
        (CATEGORY_KYC, "KYC"),
        (CATEGORY_DEPOSIT, "Deposit"),
        (CATEGORY_WITHDRAWAL, "Withdrawal"),
        (CATEGORY_PROMOTIONAL, "Promotional"),
        (CATEGORY_SYSTEM, "System"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=150)
    message = models.TextField()

    action_url = models.CharField(max_length=255, blank=True)
    action_label = models.CharField(max_length=50, blank=True)

    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "read"])]

    def __str__(self):
        return f"{self.get_category_display()} -> {self.user.email}: {self.title}"