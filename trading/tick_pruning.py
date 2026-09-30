import asyncio
import logging

from asgiref.sync import sync_to_async
from django.conf import settings

from .models import MarketInstrument, Tick

logger = logging.getLogger(__name__)


def _cfg(name, default):
    # Read at call time so a settings change takes effect without touching this file.
    return getattr(settings, name, default)


def prune_ticks_batch(keep_latest=None, batch_size=None) -> int:
    """Delete up to `batch_size` old ticks per instrument. Returns how many were deleted."""
    keep_latest = keep_latest if keep_latest is not None else _cfg("TICK_KEEP_LATEST", 10_000)
    batch_size = batch_size if batch_size is not None else _cfg("TICK_PRUNE_BATCH_SIZE", 5_000)

    deleted = 0
    for instrument_id in MarketInstrument.objects.values_list("id", flat=True):
        newest = (
            Tick.objects.filter(instrument_id=instrument_id)
            .order_by("-tick_count")
            .values_list("tick_count", flat=True)
            .first()
        )
        if newest is None:
            continue  # instrument has no ticks yet

        cutoff = newest - keep_latest  # everything below this is old
        if cutoff <= 0:
            continue  # fewer ticks than we keep, nothing to do

        # Small batches keep each DELETE short, so tick writes are never blocked for long.
        ids = list(
            Tick.objects.filter(instrument_id=instrument_id, tick_count__lt=cutoff)
            .order_by("tick_count")
            .values_list("pk", flat=True)[:batch_size]
        )
        if ids:
            Tick.objects.filter(pk__in=ids).delete()
            deleted += len(ids)
    return deleted


async def prune_ticks_forever():
    """Background loop run alongside the tick engines (see run_all_engines)."""
    while True:
        try:
            while True:
                deleted = await sync_to_async(prune_ticks_batch)()
                if not deleted:
                    break
                logger.info("Pruned %d old ticks", deleted)
                await asyncio.sleep(0.2)  # let the engines write their ticks between batches
        except Exception:
            # Never let a pruning hiccup take the price engine down with it.
            logger.exception("Tick pruning failed; will retry next cycle")
        await asyncio.sleep(_cfg("TICK_PRUNE_INTERVAL_SECONDS", 300))