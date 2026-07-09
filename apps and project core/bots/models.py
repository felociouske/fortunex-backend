from django.db import models
from django.conf import settings


class AutomationProduct(models.Model):
    """
    A purchasable bot or AI tier. Unified into one model (rather than
    separate Bot/AI tables) because they share identical purchase and
    win-chance mechanics -- the only real difference is `kind`, and a
    user may only ever have ONE automation (bot or AI) active at a time,
    which is far simpler to enforce against a single table.

    `tier` is the ordering used for "most recently purchased / highest
    tier" comparisons and for the strict contract-unlock progression
    (see CONTRACT_UNLOCK_ORDER below) -- it is NOT the primary key, so
    admins can freely reorder/rename products without renumbering IDs.
    """
    KIND_BOT = "BOT"
    KIND_AI = "AI"
    KIND_CHOICES = [
        (KIND_BOT, "Trading Bot"),
        (KIND_AI, "Trading AI"),
    ]

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    kind = models.CharField(max_length=8, choices=KIND_CHOICES)
    tier = models.PositiveSmallIntegerField(
        help_text="Ordering within its kind, 1 = entry level. Used for upgrade comparisons."
    )
    price = models.DecimalField(max_digits=18, decimal_places=2)

    # Win-chance this automation grants while active, e.g. 0.30 = 30%.
    win_chance = models.DecimalField(max_digits=5, decimal_places=4)

    # How many contract types this tier unlocks, counting from the front
    # of CONTRACT_UNLOCK_ORDER (trading/contract_types.py). E.g. 3 means
    # Rise/Fall + Even/Odd + Higher/Lower are unlocked.
    unlocked_contract_count = models.PositiveSmallIntegerField(default=1)

    # Referral commission rate paid to the REFERRER when a user they
    # referred buys this product, e.g. 0.10 = 10% of `price`.
    commission_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.10)

    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["kind", "tier"]
        unique_together = [("kind", "tier")]

    def __str__(self):
        return f"{self.get_kind_display()} {self.tier} — {self.name} ({self.win_chance * 100:.0f}%)"


class UserAutomation(models.Model):
    """
    A user's purchase of one AutomationProduct. Multiple rows can exist
    per user over time (purchase history), but at most ONE row per user
    has `active=True` at any given moment -- enforced in the purchase
    view, not at the DB level, since SQLite can't express a partial
    unique constraint cleanly here.

    Buying a new bot or AI deactivates whichever automation (bot OR AI)
    was previously active, per the "most recently purchased wins" rule.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="automations"
    )
    product = models.ForeignKey(AutomationProduct, on_delete=models.PROTECT)
    purchased_at = models.DateTimeField(auto_now_add=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-purchased_at"]
        indexes = [models.Index(fields=["user", "active"])]

    def __str__(self):
        return f"{self.user.email} / {self.product.name} [{'active' if self.active else 'inactive'}]"