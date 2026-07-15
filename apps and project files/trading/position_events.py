"""
Broadcasts position lifecycle events (opened / mark / settled) to the
owning user's `positions_user_<id>` channel group.

This exists as one shared place because a TradePosition can be created
from three different call sites with three different sync/async
contexts:
  - OpenContractView.post()        -- sync (regular DRF view)
  - StartBotRunView.post()         -- sync (regular DRF view)
  - botrun_engine._open_next_contract() -- called from async code
      (the price engine's tick loop)

Without a single shared helper, "broadcast that a position opened"
would need three separate sync/async-bridging implementations that
could easily drift out of sync with each other.
"""
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def broadcast_position_opened(position):
    """
    Call this right after creating a TradePosition, from sync code
    (Django views). Safe to call even if Channels/Redis is briefly
    unavailable -- a failed broadcast should never block opening a
    real trade, since the REST response and the open-positions list
    endpoint remain the source of truth regardless.
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            f"positions_user_{position.user_id}",
            {"type": "position.message", "data": _opened_event(position)},
        )
    except Exception:
        # Broadcasting is a best-effort live-UI nicety, not part of the
        # trade's correctness -- never let a Redis/Channels hiccup
        # surface as a failed trade to the user.
        pass


async def broadcast_position_opened_async(position, channel_layer):
    """Same as above, for callers that are already async (the price engine's tick loop)."""
    if channel_layer is None:
        return
    try:
        await channel_layer.group_send(
            f"positions_user_{position.user_id}",
            {"type": "position.message", "data": _opened_event(position)},
        )
    except Exception:
        pass


def _opened_event(position) -> dict:
    return {
        "event": "opened",
        "id": position.id,
        "instrument_symbol": position.instrument.symbol,
        "contract_type": position.contract_type,
        "side": position.side,
        "stake": str(position.stake),
        "entry_price": str(position.entry_price),
        "current_price": str(position.current_price),
        "profit_loss": str(position.profit_loss),
        "status": position.status,
        "opened_at": position.opened_at.isoformat(),
    }