"""
Synthetic price engine — Deriv-style Volatility Index generator.

This runs as a standalone async process (started via the
`run_price_engine` management command, see management/commands/), one
loop per active MarketInstrument. Each loop:

  1. Sleeps for the instrument's tick_interval_ms.
  2. Moves the price with a random walk: a small Gaussian step sized by
     the instrument's `volatility`, with weak mean-reversion back toward
     `base_price` so the price can't drift off forever.
  3. Persists the new price as a Tick row (so the chart has history and
     tick-based contracts can be settled by counting rows).
  4. Broadcasts the tick over the `ticks_<symbol>` channel group so any
     connected TickConsumer relays it to the browser instantly.
  5. Settles any contracts whose duration has elapsed (tick-count or
     wall-clock, depending on duration_unit).

This is intentionally simple — no external market data dependency, no
options-pricing model. It just needs to look and feel like a live,
moving market for Rise/Fall contracts to settle against.
"""
import asyncio
import random
from decimal import Decimal, ROUND_HALF_UP

from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from django.utils import timezone

from .models import MarketInstrument, Tick, TradePosition

TICK_DECIMALS = Decimal("0.000001")


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(TICK_DECIMALS, rounding=ROUND_HALF_UP)


class InstrumentEngine:
    """Runs the tick loop for exactly one instrument."""

    def __init__(self, instrument_id: int):
        self.instrument_id = instrument_id
        self._tick_count = 0
        self._price = None

    async def run(self):
        channel_layer = get_channel_layer()

        instrument = await sync_to_async(MarketInstrument.objects.get)(id=self.instrument_id)
        self._price = Decimal(instrument.base_price)
        self._tick_count = await self._get_last_tick_count()

        while True:
            instrument = await sync_to_async(MarketInstrument.objects.get)(id=self.instrument_id)
            if not instrument.active:
                await asyncio.sleep(2)
                continue

            self._step(instrument)
            self._tick_count += 1

            tick = await self._save_tick(instrument)
            await channel_layer.group_send(
                f"ticks_{instrument.symbol}",
                {
                    "type": "tick.message",
                    "data": {
                        "symbol": instrument.symbol,
                        "price": str(tick.price),
                        "tick_count": tick.tick_count,
                        "timestamp": tick.created_at.isoformat(),
                    },
                },
            )

            await self._settle_due_contracts(instrument, tick, channel_layer)

            await asyncio.sleep(instrument.tick_interval_ms / 1000)

    def _step(self, instrument: MarketInstrument):
        """One random-walk step with weak mean reversion toward base_price."""
        vol = float(instrument.volatility) / 100  # e.g. 0.1 -> 0.001
        pct_move = random.gauss(0, vol)

        base = float(instrument.base_price)
        current = float(self._price)
        reversion = (base - current) / base * 0.01  # tiny pull toward base

        new_price = current * (1 + pct_move + reversion)
        self._price = _quantize(Decimal(str(new_price)))

    async def _get_last_tick_count(self) -> int:
        last = await sync_to_async(
            lambda: Tick.objects.filter(instrument_id=self.instrument_id).order_by("-tick_count").first()
        )()
        return last.tick_count if last else 0

    async def _save_tick(self, instrument) -> Tick:
        return await sync_to_async(Tick.objects.create)(
            instrument=instrument,
            price=self._price,
            tick_count=self._tick_count,
        )

    async def _settle_due_contracts(self, instrument, tick, channel_layer):
        from .settlement import settle_position  # local import avoids circular import

        due = await sync_to_async(list)(
            TradePosition.objects.filter(
                instrument=instrument,
                status=TradePosition.STATUS_OPEN,
            )
        )
        for position in due:
            is_due = False
            if position.duration_unit == TradePosition.DURATION_TICKS:
                ticks_elapsed = self._tick_count - (position.entry_tick_count or 0)
                is_due = ticks_elapsed >= position.duration_value
            else:
                is_due = position.expires_at is not None and timezone.now() >= position.expires_at

            if is_due:
                            settled_position = await sync_to_async(settle_position)(position, exit_price=tick.price)
                            await channel_layer.group_send(
                                f"positions_user_{position.user_id}",
                                {
                                    "type": "position.message",
                                    "data": {
                                        "event": "settled",
                                        "id": settled_position.id,
                                        "status": settled_position.status,
                                        "profit_loss": str(settled_position.profit_loss),
                                        "exit_price": str(settled_position.exit_price),
                                    },
                                },
                            )

                            from .botrun_engine import handle_settled_position_for_bot_run
                            await handle_settled_position_for_bot_run(settled_position, channel_layer)
            else:
                # Live mark-to-market push so the open positions panel can
                # show a moving (unrealised) P/L before settlement.
                unrealised = _unrealised_pl(position, tick.price)
                await channel_layer.group_send(
                    f"positions_user_{position.user_id}",
                    {
                        "type": "position.message",
                        "data": {
                            "event": "mark",
                            "id": position.id,
                            "current_price": str(tick.price),
                            "profit_loss": str(unrealised),
                        },
                    },
                )


def _unrealised_pl(position: TradePosition, current_price: Decimal) -> Decimal:
    """Best-effort live P/L estimate before settlement (Rise/Fall only, for now)."""
    direction = 1 if position.side in ("BUY", "RISE") else -1
    price_diff_pct = (current_price - position.entry_price) / position.entry_price
    pl = position.stake * price_diff_pct * direction * Decimal(10)  # amplified for visual feedback only
    return _quantize_money(pl)


def _quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def run_all_engines():
    """Discover all active instruments and run one engine loop per instrument, concurrently."""
    instrument_ids = await sync_to_async(
        lambda: list(MarketInstrument.objects.filter(active=True).values_list("id", flat=True))
    )()
    if not instrument_ids:
        return
    engines = [InstrumentEngine(iid) for iid in instrument_ids]
    await asyncio.gather(*(e.run() for e in engines))