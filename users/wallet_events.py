"""
Pushes a user's current wallet balances to their `wallet_user_<id>`
channel group, so every open browser tab shows the new balance the
moment it changes.

Design notes:
  - Messages carry ABSOLUTE balances, never deltas. If a message is
    missed or arrives late, the next one simply corrects the number.
  - The balances are re-read from the database at broadcast time
    instead of taken from the Wallet instance that was just saved.
    Callers save with update_fields (e.g. only "real_balance"), so the
    in-memory instance can hold stale values for the other two fields.
  - Field names and string formatting match WalletSerializer, so the
    frontend can merge a message straight into `user.wallet`.
"""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Wallet

logger = logging.getLogger(__name__)


def wallet_snapshot(user_id):
    """Fresh committed balances for one user as a wallet_update event, or None if no wallet."""

    row = (
        Wallet.objects.filter(user_id=user_id)
        .values("real_balance", "deposit_balance", "yield_balance", "currency", "updated_at")
        .first()
    )
    if row is None:
        return None
    return {
        "event": "wallet_update",
        # f"{x:.2f}" matches DRF's DecimalField output ("12.30", not "12.3")
        "real_balance": f"{row['real_balance']:.2f}",
        "deposit_balance": f"{row['deposit_balance']:.2f}",
        "yield_balance": f"{row['yield_balance']:.2f}",
        "currency": row["currency"],
        "updated_at": row["updated_at"].isoformat(),
    }


def broadcast_wallet_update(user_id):
    """
    Sync entry point (wallet saves happen in sync code: views, admin,
    and sync_to_async threads in the price engine). Best-effort: a
    Redis/Channels hiccup must never break a deposit or a trade, and
    the REST balance endpoint stays the source of truth.
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        data = wallet_snapshot(user_id)
        if data is None:
            return
        async_to_sync(channel_layer.group_send)(
            f"wallet_user_{user_id}",
            {"type": "wallet.message", "data": data},
        )
    except Exception:
        logger.warning("Wallet broadcast failed for user %s", user_id, exc_info=True)

        