from django.db import models
from django.conf import settings


class MarketInstrument(models.Model):
    name = models.CharField(max_length=120)
    symbol = models.CharField(max_length=32, unique=True)
    category = models.CharField(max_length=64)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.symbol})"


class TradePosition(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="positions")
    instrument = models.ForeignKey(MarketInstrument, on_delete=models.PROTECT)
    side = models.CharField(max_length=8, choices=[("BUY", "Buy"), ("SELL", "Sell")])
    opened_at = models.DateTimeField(auto_now_add=True)
    stake = models.DecimalField(max_digits=18, decimal_places=2)
    entry_price = models.DecimalField(max_digits=18, decimal_places=6)
    current_price = models.DecimalField(max_digits=18, decimal_places=6)
    profit_loss = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(max_length=32, default="OPEN")

    def __str__(self):
        return f"{self.user.email} | {self.instrument.symbol} | {self.status}"
