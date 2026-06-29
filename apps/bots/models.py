from django.db import models
from django.conf import settings


class BotProduct(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=18, decimal_places=2)
    category = models.CharField(max_length=80, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class PurchasedBot(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="purchased_bots")
    bot = models.ForeignKey(BotProduct, on_delete=models.PROTECT)
    purchased_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.email} / {self.bot.name}"