"""
Broadcasts M-Pesa deposit status changes to the owning user's
`deposit_user_<id>` channel group -- mirrors trading/position_events.py's
sync-to-async bridging pattern, for the same reason: resolve_deposit_result()
is called from plain (synchronous) Django views.
"""
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def broadcast_deposit_update(deposit):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            f"deposit_user_{deposit.user_id}",
            {"type": "deposit.message", "data": _deposit_event(deposit)},
        )
    except Exception:
        # Best-effort live-UI nicety -- the frontend's one-shot status
        # fallback remains the source of truth if this doesn't arrive.
        pass


def _deposit_event(deposit) -> dict:
    return {
        "event": "deposit_update",
        "id": deposit.id,
        "checkout_request_id": deposit.checkout_request_id,
        "status": deposit.status,
        "amount": str(deposit.amount),
        "currency": deposit.currency,
        "kes_amount": str(deposit.kes_amount) if deposit.kes_amount is not None else None,
        "mpesa_receipt_number": deposit.mpesa_receipt_number,
        "result_desc": deposit.result_desc,
    }