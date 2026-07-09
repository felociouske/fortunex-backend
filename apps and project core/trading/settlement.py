"""
Contract settlement logic, one function per contract type.

Every contract type settles via the SAME mechanism: a weighted coin
flip using the user's active automation tier's win_chance (see
win_chance.py). This is a deliberate product decision -- the platform
controls win probability directly rather than leaving outcomes to
genuine price movement. The underlying synthetic price still moves
and entry/exit prices are still recorded (for chart realism and
because `prediction` needs an exit price/digit to describe a result
against), but the WON/LOST outcome itself comes from the coin flip,
not from comparing entry_price to exit_price.

Keeping each contract type in its own function (rather than one
big if/elif) means each type's "what does a win/loss actually look
like" cosmetics (e.g. which digit the price ended on, which barrier
side it landed on) can be computed independently, even though they
all share the same underlying probability.
"""
import random
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from .models import TradePosition


def _quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _last_digit(price: Decimal) -> int:
    """Last digit of a price's decimal representation, used for digit-based contracts."""
    digits = str(price).replace(".", "").replace("-", "")
    return int(digits[-1])


def _coin_flip(win_chance: float) -> bool:
    return random.random() < win_chance


def _settle_rise_fall(position: TradePosition, exit_price: Decimal, won: bool):
    """Rise wins -> exit_price set above entry; Fall wins -> exit_price set below. Cosmetic only."""
    predicted_up = position.side in ("BUY", "RISE")
    if won:
        # Make the recorded exit price visually consistent with a win,
        # since the real engine-generated price may not have actually
        # moved the "correct" way -- the coin flip decided the outcome,
        # this just makes the displayed numbers tell a consistent story.
        return exit_price if (exit_price > position.entry_price) == predicted_up else (
            position.entry_price + Decimal("0.000001") if predicted_up else position.entry_price - Decimal("0.000001")
        )
    else:
        return exit_price if (exit_price > position.entry_price) != predicted_up else (
            position.entry_price - Decimal("0.000001") if predicted_up else position.entry_price + Decimal("0.000001")
        )


def _settle_even_odd(position: TradePosition, exit_price: Decimal, won: bool):
    parity = position.prediction.get("parity", "EVEN")
    digit = _last_digit(exit_price)
    is_even = digit % 2 == 0
    matches = is_even if parity == "EVEN" else not is_even
    if matches == won:
        return exit_price
    # Nudge the price by 1 unit in the last decimal place to flip parity
    # while keeping the value visually close to the real engine price.
    return exit_price + Decimal("0.000001") if won != matches else exit_price


def _settle_generic_cosmetic(position: TradePosition, exit_price: Decimal, won: bool):
    """
    Shared fallback for contract types whose win/loss cosmetics aren't
    worth a fully bespoke function yet (Higher/Lower, Over/Under,
    Matches/Differs, Touch/No-Touch) -- the coin flip already decided
    `won`; we just record the real exit price as-is, since unlike
    Rise/Fall or Even/Odd there's no cheap visual nudge that makes
    these consistently "look right" without much more chart-level
    barrier/digit simulation. Acceptable for now: the WON/LOST status
    and payout are always correct: only the displayed exit price may
    not visibly "explain" the result for these four types yet.
    """
    return exit_price


SETTLEMENT_COSMETICS = {
    TradePosition.CONTRACT_RISE_FALL: _settle_rise_fall,
    TradePosition.CONTRACT_EVEN_ODD: _settle_even_odd,
    TradePosition.CONTRACT_HIGHER_LOWER: _settle_generic_cosmetic,
    TradePosition.CONTRACT_OVER_UNDER: _settle_generic_cosmetic,
    TradePosition.CONTRACT_MATCHES_DIFFERS: _settle_generic_cosmetic,
    TradePosition.CONTRACT_TOUCH_NO_TOUCH: _settle_generic_cosmetic,
}


@transaction.atomic
def settle_position(position: TradePosition, exit_price: Decimal) -> TradePosition:
    """
    Settle one open contract: roll the weighted coin flip using the
    win_chance that was locked in at contract-open time (stored on
    `win_chance_applied`, NOT re-resolved here), credit/debit the
    user's wallet, and persist the final state.

    Using the win_chance captured at open time (rather than the user's
    CURRENT active tier) matters: if a user buys a better bot mid-trade,
    that shouldn't retroactively change the odds of a contract they
    already opened under the old tier.

    Safe to call more than once for the same position (a second call is
    a no-op) so the price engine's loop doesn't need to worry about
    double-settlement.
    """
    position = TradePosition.objects.select_for_update().get(id=position.id)
    if position.status != TradePosition.STATUS_OPEN:
        return position

    win_chance = float(position.win_chance_applied) if position.win_chance_applied is not None else 0.03
    won = _coin_flip(win_chance)

    cosmetic_fn = SETTLEMENT_COSMETICS.get(position.contract_type, _settle_generic_cosmetic)
    display_exit_price = cosmetic_fn(position, exit_price, won)

    if won:
        payout = position.stake * (Decimal(1) + position.payout_ratio)
        profit_loss = _quantize_money(payout - position.stake)
        status = TradePosition.STATUS_WON
    else:
        profit_loss = _quantize_money(-position.stake)
        status = TradePosition.STATUS_LOST

    position.status = status
    position.profit_loss = profit_loss
    position.exit_price = display_exit_price
    position.current_price = display_exit_price
    position.closed_at = timezone.now()
    position.save(update_fields=[
        "status", "profit_loss", "exit_price", "current_price", "closed_at",
    ])

    if status == TradePosition.STATUS_WON:
        wallet = position.user.wallet
        payout = position.stake + profit_loss
        wallet.real_balance = wallet.real_balance + payout
        wallet.save(update_fields=["real_balance", "updated_at"])

    return position