"""
Bot-run automation: after a BotRun's current contract settles, either
opens the next identical contract or stops the run, depending on stop
conditions (manual stop, stop-loss, take-profit, insufficient funds).

Hooked into the price engine's per-tick settlement loop (see engine.py)
rather than running as its own separate process -- a bot run only ever
needs to react the instant ITS contract settles, and the price engine
already visits every open contract on every tick to check for that.

Each contract a bot run opens is a completely normal TradePosition,
going through the exact same KYC gate, combined-pool stake debit, and
weighted-coin-flip settlement as a manually-placed trade (see
trading/serializers.py, wallet_utils.py, settlement.py). A bot run is
just something that keeps calling "open contract" automatically.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import BotRun, Tick, TradePosition
from .wallet_utils import check_stake_affordable, debit_stake, InsufficientFunds
from .win_chance import resolve_active_tier


async def handle_settled_position_for_bot_run(position: TradePosition, channel_layer):
    """
    Called by the price engine immediately after `position` settles.
    No-op if this position isn't the current contract of any running
    BotRun. Otherwise, updates the run's cumulative P/L, checks stop
    conditions, and either opens the next contract or stops the run --
    broadcasting a bot_run status event either way, AND a position
    "opened" event for the new contract (if one was opened) so the
    frontend's Open Positions panel discovers it immediately rather
    than waiting for its next periodic poll.
    """
    from asgiref.sync import sync_to_async
    from .position_events import broadcast_position_opened_async

    run = await sync_to_async(_get_run_for_position)(position)
    if run is None:
        return

    run, new_position = await sync_to_async(_advance_run)(run, position)

    if new_position is not None:
        await broadcast_position_opened_async(new_position, channel_layer)

    if run.status == BotRun.STATUS_RUNNING:
        await channel_layer.group_send(
            f"botrun_user_{run.user_id}",
            {"type": "botrun.message", "data": _run_event(run, event="trade_settled")},
        )
    else:
        await channel_layer.group_send(
            f"botrun_user_{run.user_id}",
            {"type": "botrun.message", "data": _run_event(run, event="stopped")},
        )


def _get_run_for_position(position: TradePosition) -> BotRun | None:
    return BotRun.objects.filter(
        current_position=position, status=BotRun.STATUS_RUNNING
    ).select_related("user", "instrument").first()


@transaction.atomic
def _advance_run(run: BotRun, settled_position: TradePosition) -> tuple[BotRun, TradePosition | None]:
    """
    Updates cumulative P/L from the just-settled contract, checks stop
    conditions in priority order (take-profit and stop-loss before
    funds, since those are the user's deliberate limits), and either
    opens the next contract or marks the run stopped.

    Returns (run, new_position): callers must use the returned `run`,
    not their original argument, since the row is re-fetched and
    mutated on a fresh instance here (select_for_update requires a new
    query). `new_position` is the freshly-opened contract if one was
    opened, or None if the run stopped instead -- the async caller
    uses this to broadcast an "opened" event from proper async context,
    since this function itself runs via sync_to_async and can't await.
    """
    run = BotRun.objects.select_for_update().get(id=run.id)
    if run.status != BotRun.STATUS_RUNNING:
        return run, None  # already stopped by a concurrent request (e.g. manual stop)

    run.cumulative_profit_loss = run.cumulative_profit_loss + settled_position.profit_loss
    run.trades_count = run.trades_count + 1
    run.current_position = None

    if run.cumulative_profit_loss >= run.take_profit:
        run.status = BotRun.STATUS_STOPPED_TAKE_PROFIT
        run.stopped_at = timezone.now()
        run.save(update_fields=[
            "cumulative_profit_loss", "trades_count", "current_position", "status", "stopped_at",
        ])
        return run, None

    if run.cumulative_profit_loss <= -run.stop_loss:
        run.status = BotRun.STATUS_STOPPED_STOP_LOSS
        run.stopped_at = timezone.now()
        run.save(update_fields=[
            "cumulative_profit_loss", "trades_count", "current_position", "status", "stopped_at",
        ])
        return run, None

    try:
        next_position = _open_next_contract(run)
        run.current_position = next_position
        run.save(update_fields=["cumulative_profit_loss", "trades_count", "current_position"])
        return run, next_position
    except InsufficientFunds:
        run.status = BotRun.STATUS_STOPPED_INSUFFICIENT_FUNDS
        run.stopped_at = timezone.now()
        run.save(update_fields=[
            "cumulative_profit_loss", "trades_count", "current_position", "status", "stopped_at",
        ])
        return run, None


def _open_next_contract(run: BotRun) -> TradePosition:
    """Opens one more contract using the run's frozen config. Raises InsufficientFunds if unaffordable."""
    latest_tick = Tick.objects.filter(instrument=run.instrument).order_by("-tick_count").first()
    if latest_tick is None:
        raise InsufficientFunds("No live price available.")

    wallet = run.user.wallet.__class__.objects.select_for_update().get(user=run.user)
    check_stake_affordable(wallet, run.stake)
    debit_stake(wallet, run.stake)
    wallet.save(update_fields=["real_balance", "deposit_balance", "updated_at"])

    tier = resolve_active_tier(run.user)

    return TradePosition.objects.create(
        user=run.user,
        instrument=run.instrument,
        contract_type=run.contract_type,
        side=run.side,
        prediction=run.prediction,
        duration_unit=run.duration_unit,
        duration_value=run.duration_value,
        stake=run.stake,
        entry_price=latest_tick.price,
        current_price=latest_tick.price,
        entry_tick_count=latest_tick.tick_count,
        win_chance_applied=Decimal(str(tier.win_chance)),
        win_chance_source=tier.source_label,
        expires_at=(
            timezone.now() + timezone.timedelta(seconds=run.duration_value)
            if run.duration_unit == TradePosition.DURATION_SECONDS
            else None
        ),
    )


def _run_event(run: BotRun, event: str) -> dict:
    return {
        "event": event,
        "id": run.id,
        "status": run.status,
        "cumulative_profit_loss": str(run.cumulative_profit_loss),
        "trades_count": run.trades_count,
        "current_position_id": run.current_position_id,
    }