from decimal import Decimal

from rest_framework import serializers

from .models import MarketInstrument, TradePosition, Tick, BotRun
from .wallet_utils import check_stake_affordable, InsufficientFunds


class MarketInstrumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketInstrument
        fields = [
            "id", "name", "symbol", "category", "description", "active",
            "base_price", "volatility", "tick_interval_ms",
        ]


class TickSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tick
        fields = ["price", "tick_count", "created_at"]


class TradePositionSerializer(serializers.ModelSerializer):
    """Read serializer used for listing open/settled positions."""
    instrument = MarketInstrumentSerializer(read_only=True)

    class Meta:
        model = TradePosition
        fields = [
            "id", "instrument", "contract_type", "side", "prediction",
            "duration_unit", "duration_value",
            "opened_at", "expires_at", "closed_at",
            "stake", "payout_ratio",
            "entry_price", "current_price", "exit_price",
            "win_chance_applied", "win_chance_source",
            "profit_loss", "status",
        ]


# Which prediction keys each non-Rise/Fall contract type requires, and
# the allowed values for choice-like keys. Rise/Fall isn't listed here
# since it uses the dedicated `side` field instead.
PREDICTION_SCHEMAS = {
    TradePosition.CONTRACT_EVEN_ODD: {"parity": ["EVEN", "ODD"]},
    TradePosition.CONTRACT_HIGHER_LOWER: {"direction": ["HIGHER", "LOWER"], "barrier": None},
    TradePosition.CONTRACT_OVER_UNDER: {"direction": ["OVER", "UNDER"], "digit": None},
    TradePosition.CONTRACT_MATCHES_DIFFERS: {"mode": ["MATCHES", "DIFFERS"], "digit": None},
    TradePosition.CONTRACT_TOUCH_NO_TOUCH: {"mode": ["TOUCH", "NO_TOUCH"], "barrier": None},
}


class OpenContractSerializer(serializers.Serializer):
    """
    Write serializer for POST /trading/contracts/ -- opens a new contract
    of any of the 6 supported types. `side` is used for Rise/Fall;
    `prediction` carries the type-specific parameters for the other 5
    (see PREDICTION_SCHEMAS above and models.py for the exact shape).

    Contract-type unlock tiers are NOT enforced here -- per product
    decision, unlocks are an upsell/UI signal only. Any KYC-verified
    user can attempt any contract type regardless of their automation
    tier; the tier only affects win_chance at settlement.
    """
    instrument_id = serializers.IntegerField()
    contract_type = serializers.ChoiceField(
        choices=TradePosition.CONTRACT_CHOICES, default=TradePosition.CONTRACT_RISE_FALL
    )
    side = serializers.ChoiceField(choices=["RISE", "FALL"], required=False)
    prediction = serializers.JSONField(required=False, default=dict)
    duration_unit = serializers.ChoiceField(choices=TradePosition.DURATION_UNIT_CHOICES)
    duration_value = serializers.IntegerField(min_value=1)
    stake = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))

    def validate_instrument_id(self, value):
        try:
            instrument = MarketInstrument.objects.get(id=value, active=True)
        except MarketInstrument.DoesNotExist:
            raise serializers.ValidationError("This instrument is not available for trading.")
        self._instrument = instrument
        return value

    def validate(self, data):
        request = self.context["request"]
        user = request.user
        contract_type = data["contract_type"]

        if not user.is_kyc_verified:
            raise serializers.ValidationError(
                "Your account must complete KYC verification before you can trade."
            )

        _validate_contract_config(contract_type, data.get("side"), data.get("prediction"))

        already_open = TradePosition.objects.filter(
            user=user, instrument_id=data["instrument_id"], status=TradePosition.STATUS_OPEN,
        ).exists()
        if already_open:
            raise serializers.ValidationError(
                "You already have an open contract on this instrument. "
                "Wait for it to settle before opening another."
            )

        # Stake funding rule: real_balance + deposit_balance are treated
        # as one combined pool. Reject only if the COMBINED total can't
        # cover the stake -- see wallet_utils.py for the actual debit
        # logic (drains real_balance first, remainder from deposit).
        wallet = getattr(user, "wallet", None)
        if wallet is None:
            raise serializers.ValidationError("No wallet found for this account.")

        try:
            check_stake_affordable(wallet, data["stake"])
        except InsufficientFunds as exc:
            raise serializers.ValidationError(str(exc))

        return data


def _validate_contract_config(contract_type, side, prediction):
    """
    Shared per-contract-type parameter validation, used by both
    OpenContractSerializer (single manual trade) and
    StartBotRunSerializer (frozen config repeated every loop) so the
    two can never validate contract configs differently.
    Raises serializers.ValidationError on any problem.
    """
    if contract_type == TradePosition.CONTRACT_RISE_FALL:
        if not side:
            raise serializers.ValidationError({"side": "Rise/Fall contracts require a side (RISE or FALL)."})
        return

    schema = PREDICTION_SCHEMAS[contract_type]
    prediction = prediction or {}
    for key, allowed_values in schema.items():
        if key not in prediction:
            raise serializers.ValidationError(
                {"prediction": f"{contract_type} contracts require a '{key}' value."}
            )
        if allowed_values is not None and prediction[key] not in allowed_values:
            raise serializers.ValidationError({"prediction": f"'{key}' must be one of {allowed_values}."})
        if key == "digit":
            try:
                digit = int(prediction["digit"])
            except (TypeError, ValueError):
                raise serializers.ValidationError({"prediction": "'digit' must be an integer 0-9."})
            if not (0 <= digit <= 9):
                raise serializers.ValidationError({"prediction": "'digit' must be between 0 and 9."})


class BotRunSerializer(serializers.ModelSerializer):
    """Read serializer for an in-progress or finished bot run."""
    instrument = MarketInstrumentSerializer(read_only=True)

    class Meta:
        model = BotRun
        fields = [
            "id", "instrument", "contract_type", "side", "prediction",
            "duration_unit", "duration_value", "stake", "stop_loss", "take_profit",
            "cumulative_profit_loss", "trades_count", "status",
            "started_at", "stopped_at", "current_position",
        ]


class StartBotRunSerializer(serializers.Serializer):
    """
    Write serializer for POST /trading/botrun/start/. Freezes a contract
    config (instrument + contract_type + side/prediction + duration) plus
    stake/stop_loss/take_profit into a new running BotRun. Only an
    active automation of kind=BOT can start one -- AIs are advisory-only
    and never auto-submit trades (enforced in the view).
    """
    instrument_id = serializers.IntegerField()
    contract_type = serializers.ChoiceField(
        choices=TradePosition.CONTRACT_CHOICES, default=TradePosition.CONTRACT_RISE_FALL
    )
    side = serializers.ChoiceField(choices=["RISE", "FALL"], required=False)
    prediction = serializers.JSONField(required=False, default=dict)
    duration_unit = serializers.ChoiceField(choices=TradePosition.DURATION_UNIT_CHOICES)
    duration_value = serializers.IntegerField(min_value=1)
    stake = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))
    stop_loss = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))
    take_profit = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))

    def validate_instrument_id(self, value):
        try:
            instrument = MarketInstrument.objects.get(id=value, active=True)
        except MarketInstrument.DoesNotExist:
            raise serializers.ValidationError("This instrument is not available for trading.")
        self._instrument = instrument
        return value

    def validate(self, data):
        request = self.context["request"]
        user = request.user

        if not user.is_kyc_verified:
            raise serializers.ValidationError(
                "Your account must complete KYC verification before you can trade."
            )

        _validate_contract_config(data["contract_type"], data.get("side"), data.get("prediction"))

        already_running = BotRun.objects.filter(user=user, status=BotRun.STATUS_RUNNING).exists()
        if already_running:
            raise serializers.ValidationError(
                "You already have a bot run in progress. Stop it before starting a new one."
            )

        already_open_manual = TradePosition.objects.filter(
            user=user, instrument_id=data["instrument_id"], status=TradePosition.STATUS_OPEN,
        ).exists()
        if already_open_manual:
            raise serializers.ValidationError(
                "You have an open manual contract on this instrument. "
                "Wait for it to settle before starting a bot run."
            )

        wallet = getattr(user, "wallet", None)
        if wallet is None:
            raise serializers.ValidationError("No wallet found for this account.")

        try:
            check_stake_affordable(wallet, data["stake"])
        except InsufficientFunds as exc:
            raise serializers.ValidationError(str(exc))

        return data