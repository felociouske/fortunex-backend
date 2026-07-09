from django.db import models
from django.conf import settings


class MarketInstrument(models.Model):
    name = models.CharField(max_length=120)
    symbol = models.CharField(max_length=32, unique=True)
    category = models.CharField(max_length=64)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    base_price = models.DecimalField(max_digits=18, decimal_places=6, default=1000)
    volatility = models.DecimalField(
        max_digits=6, decimal_places=4, default=0.1,
        help_text="Standard deviation of each tick's price move, as a percentage (e.g. 0.1 = 0.1%)."
    )
    tick_interval_ms = models.PositiveIntegerField(
        default=1000, help_text="Milliseconds between ticks for this instrument."
    )

    def __str__(self):
        return f"{self.name} ({self.symbol})"


class TradePosition(models.Model):
    """
    A single trading contract. Only one OPEN contract per (user, instrument)
    is allowed at a time — enforced in the view/serializer layer, not here,
    since SQLite can't express that as a DB constraint cleanly alongside
    historical CLOSED rows.

    Settlement for every contract type is a weighted coin flip using the
    user's active automation tier's win_chance (see services.py /
    settlement.py) — NOT a real price comparison. The underlying price
    still moves on the chart for visual realism, and `entry_price` /
    `exit_price` are still recorded, but they do not determine the
    outcome. This is a deliberate product decision, not a bug.
    """

    STATUS_OPEN = "OPEN"
    STATUS_WON = "WON"
    STATUS_LOST = "LOST"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_WON, "Won"),
        (STATUS_LOST, "Lost"),
    ]

    CONTRACT_RISE_FALL = "RISE_FALL"
    CONTRACT_EVEN_ODD = "EVEN_ODD"
    CONTRACT_HIGHER_LOWER = "HIGHER_LOWER"
    CONTRACT_OVER_UNDER = "OVER_UNDER"
    CONTRACT_MATCHES_DIFFERS = "MATCHES_DIFFERS"
    CONTRACT_TOUCH_NO_TOUCH = "TOUCH_NO_TOUCH"
    CONTRACT_CHOICES = [
        (CONTRACT_RISE_FALL, "Rise/Fall"),
        (CONTRACT_EVEN_ODD, "Even/Odd"),
        (CONTRACT_HIGHER_LOWER, "Higher/Lower"),
        (CONTRACT_OVER_UNDER, "Over/Under"),
        (CONTRACT_MATCHES_DIFFERS, "Matches/Differs"),
        (CONTRACT_TOUCH_NO_TOUCH, "Touch/No Touch"),
    ]

    DURATION_TICKS = "ticks"
    DURATION_SECONDS = "seconds"
    DURATION_UNIT_CHOICES = [
        (DURATION_TICKS, "Ticks"),
        (DURATION_SECONDS, "Seconds"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="positions")
    instrument = models.ForeignKey(MarketInstrument, on_delete=models.PROTECT)

    contract_type = models.CharField(max_length=32, choices=CONTRACT_CHOICES, default=CONTRACT_RISE_FALL)
    side = models.CharField(
        max_length=8,
        choices=[("BUY", "Buy"), ("SELL", "Sell"), ("RISE", "Rise"), ("FALL", "Fall")],
        blank=True,
        help_text="Legacy/Rise-Fall direction field. Other contract types use `prediction` instead.",
    )

    prediction = models.JSONField(default=dict, blank=True)

    duration_unit = models.CharField(max_length=10, choices=DURATION_UNIT_CHOICES, default=DURATION_TICKS)
    duration_value = models.PositiveIntegerField(default=5, help_text="Number of ticks, or number of seconds.")

    opened_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="For time-based contracts: when this contract settles."
    )
    entry_tick_count = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="For tick-based contracts: the instrument's tick counter value at entry."
    )

    stake = models.DecimalField(max_digits=18, decimal_places=2)
    payout_ratio = models.DecimalField(
        max_digits=6, decimal_places=4, default=0.95,
        help_text="Payout multiplier on win, e.g. 0.95 = stake back plus 95% profit."
    )

    entry_price = models.DecimalField(max_digits=18, decimal_places=6)
    current_price = models.DecimalField(max_digits=18, decimal_places=6)
    exit_price = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)

    win_chance_applied = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    win_chance_source = models.CharField(max_length=100, blank=True)

    profit_loss = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_OPEN)
    closed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.email} | {self.instrument.symbol} | {self.status}"

    class Meta:
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["instrument", "status"]),
        ]


class Tick(models.Model):
    """
    One price tick for an instrument. Written by the price engine on every
    tick so the chart has history to draw on page load, and so tick-based
    contracts can be settled by counting rows rather than trusting client
    clocks. Old rows can be pruned periodically — this is a hot table.
    """
    instrument = models.ForeignKey(MarketInstrument, on_delete=models.CASCADE, related_name="ticks")
    price = models.DecimalField(max_digits=18, decimal_places=6)
    tick_count = models.PositiveBigIntegerField(help_text="Monotonically increasing counter, per instrument.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["instrument", "tick_count"])]
        ordering = ["tick_count"]

    def __str__(self):
        return f"{self.instrument.symbol} #{self.tick_count} = {self.price}"


class BotRun(models.Model):
    """
    A running (or finished) bot-automation session: the user configures
    a contract once (instrument, contract_type, side/prediction,
    duration), a stake, a stop-loss, and a take-profit, then the bot
    repeatedly opens that EXACT contract over and over -- waiting for
    each one to settle before opening the next -- until one of the stop
    conditions is hit. Config is frozen at creation; changing the
    Contracts panel UI while a run is active has no effect on it (per
    product decision).

    AIs never get a BotRun -- per product decision, AI is advisory-only
    and never auto-submits trades. Only an active automation of
    kind=BOT can start one (enforced in the view/serializer layer).

    Each contract this run opens IS a normal TradePosition (same wallet
    debit/credit, same settlement pipeline as a manually-placed trade)
    -- this is "extra" volume on top of manual trading, not a separate
    simulated earnings stream.
    """
    STATUS_RUNNING = "RUNNING"
    STATUS_STOPPED_MANUAL = "STOPPED_MANUAL"
    STATUS_STOPPED_STOP_LOSS = "STOPPED_STOP_LOSS"
    STATUS_STOPPED_TAKE_PROFIT = "STOPPED_TAKE_PROFIT"
    STATUS_STOPPED_INSUFFICIENT_FUNDS = "STOPPED_INSUFFICIENT_FUNDS"
    STATUS_CHOICES = [
        (STATUS_RUNNING, "Running"),
        (STATUS_STOPPED_MANUAL, "Stopped by user"),
        (STATUS_STOPPED_STOP_LOSS, "Stopped — stop-loss hit"),
        (STATUS_STOPPED_TAKE_PROFIT, "Stopped — take-profit hit"),
        (STATUS_STOPPED_INSUFFICIENT_FUNDS, "Stopped — insufficient funds"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bot_runs")
    instrument = models.ForeignKey(MarketInstrument, on_delete=models.PROTECT)

    contract_type = models.CharField(max_length=32, choices=TradePosition.CONTRACT_CHOICES)
    side = models.CharField(max_length=8, blank=True)
    prediction = models.JSONField(default=dict, blank=True)
    duration_unit = models.CharField(max_length=10, choices=TradePosition.DURATION_UNIT_CHOICES)
    duration_value = models.PositiveIntegerField()

    stake = models.DecimalField(max_digits=18, decimal_places=2)
    stop_loss = models.DecimalField(
        max_digits=18, decimal_places=2,
        help_text="Stop automatically once cumulative loss reaches this amount."
    )
    take_profit = models.DecimalField(
        max_digits=18, decimal_places=2,
        help_text="Stop automatically once cumulative profit reaches this amount."
    )

    cumulative_profit_loss = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    trades_count = models.PositiveIntegerField(default=0)

    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_RUNNING)
    started_at = models.DateTimeField(auto_now_add=True)
    stopped_at = models.DateTimeField(null=True, blank=True)

    current_position = models.ForeignKey(
        TradePosition, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["user", "status"])]

    def __str__(self):
        return f"{self.user.email} bot run on {self.instrument.symbol} [{self.status}]"