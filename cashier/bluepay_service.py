"""
BluePay M-Pesa integration -- a SEPARATE payment rail from Daraja
(mpesa_service.py). No official SDK exists for BluePay, so this talks
to their REST API directly via `requests`, matching the style already
used in mpesa_service.py.

Docs referenced for this integration: https://bluepay.co.ke/public/docs.php
"""
from __future__ import annotations

import hashlib
import hmac
import re
from decimal import Decimal, ROUND_HALF_UP

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Deposit

BLUEPAY_BASE_URL = "https://bluepay.co.ke"
STK_PUSH_URL = f"{BLUEPAY_BASE_URL}/api/stk_push.php"
STATUS_URL = f"{BLUEPAY_BASE_URL}/api/payment_status.php"


# ─── Phone number handling ───────────────────────────────────────────────────
# (Intentionally duplicated from mpesa_service.py, not imported, so this
# module has zero dependency on the Daraja integration.)

def normalize_phone(raw: str) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)

    if digits.startswith("0") and len(digits) == 10:
        digits = "254" + digits[1:]
    elif digits.startswith("7") and len(digits) == 9:
        digits = "254" + digits
    elif digits.startswith("1") and len(digits) == 9:
        digits = "254" + digits
    elif digits.startswith("254") and len(digits) == 12:
        pass
    else:
        return None

    if not re.fullmatch(r"254[71]\d{8}", digits):
        return None
    return digits


# ─── Currency conversion ─────────────────────────────────────────────────────

def usd_to_kes(usd_amount: Decimal) -> Decimal:
    rate = Decimal(str(settings.USD_TO_KES_RATE))
    return (Decimal(usd_amount) * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


class BluePayError(Exception):
    """Raised for any BluePay-side failure: auth, network, or a rejected request."""


def _headers() -> dict:
    if not settings.BLUEPAY_API_SECRET:
        raise BluePayError("BluePay API secret is not configured (BLUEPAY_API_SECRET).")
    return {
        "Authorization": f"Bearer {settings.BLUEPAY_API_SECRET}",
        "Content-Type": "application/json",
    }


def send_stk_push(*, phone_number: str, kes_amount: Decimal, account_reference: str) -> dict:
    if not settings.BLUEPAY_CHANNEL_ID:
        raise BluePayError("BluePay channel_id is not configured (BLUEPAY_CHANNEL_ID).")

    payload = {
        "channel_id": settings.BLUEPAY_CHANNEL_ID,
        "phone": phone_number,
        "amount": int(kes_amount),
        "account_reference": account_reference,
    }
    try:
        resp = requests.post(STK_PUSH_URL, json=payload, headers=_headers(), timeout=30)
    except requests.RequestException as exc:
        raise BluePayError(f"Could not reach BluePay: {exc}") from exc

    try:
        data = resp.json()
    except ValueError:
        raise BluePayError(f"BluePay returned a non-JSON response (HTTP {resp.status_code}).")

    if not data.get("ok"):
        message = data.get("message") or data.get("error") or f"BluePay STK push failed (HTTP {resp.status_code})."
        raise BluePayError(message)

    return data


def query_status(*, checkout_request_id: str) -> dict:
    try:
        resp = requests.get(
            STATUS_URL,
            params={"checkout_request_id": checkout_request_id},
            headers=_headers(),
            timeout=30,
        )
    except requests.RequestException as exc:
        raise BluePayError(f"Could not reach BluePay: {exc}") from exc
    try:
        return resp.json()
    except ValueError:
        raise BluePayError(f"BluePay returned a non-JSON response (HTTP {resp.status_code}).")


def verify_webhook_signature(*, raw_body: bytes, signature_header: str) -> bool:
    """
    `signature_header` looks like 'v1=<hex hmac-sha256>', computed by
    BluePay over the RAW request body using the API secret (the same
    key used for Bearer auth -- BluePay's docs are explicit that
    webhook HMAC always uses the API secret, never Basic credentials).
    """
    if not signature_header or not settings.BLUEPAY_API_SECRET:
        return False
    match = re.fullmatch(r"v1=([a-f0-9]{64})", signature_header.strip())
    if not match:
        return False
    expected = hmac.new(settings.BLUEPAY_API_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, match.group(1))


# ─── Initiating a deposit ─────────────────────────────────────────────────────

def initiate_deposit(*, user, usd_amount: Decimal, phone_number: str) -> Deposit:
    kes_amount = usd_to_kes(usd_amount)

    deposit = Deposit.objects.create(
        user=user,
        amount=usd_amount,
        currency="USD",
        status=Deposit.STATUS_PROCESSING,
        method=Deposit.METHOD_BLUEPAY,
        phone_number=phone_number,
        kes_amount=kes_amount,
        exchange_rate=Decimal(str(settings.USD_TO_KES_RATE)),
    )

    try:
        data = send_stk_push(
            phone_number=phone_number,
            kes_amount=kes_amount,
            # BluePay requires account_reference to literally START WITH "BP"
            # (confirmed via their pay-link UI: "must start with BP") --
            # NOT buried mid-string like the old "FX-BP-..." was.
            account_reference=f"BP-{deposit.id}",
        )
    except BluePayError as exc:
        deposit.status = Deposit.STATUS_FAILED
        deposit.result_desc = str(exc)[:255]
        deposit.reviewed_at = timezone.now()
        deposit.save(update_fields=["status", "result_desc", "reviewed_at"])
        raise

    # BluePay's checkout_request_id IS Safaricom's native ws_CO_... id --
    # the same shape Daraja gives us directly. Stored in the same column
    # the Daraja flow uses, so the existing WebSocket broadcast
    # (deposit_events.py) and DepositConsumer work unmodified.
    deposit.checkout_request_id = data.get("checkout_request_id") or ""
    deposit.save(update_fields=["checkout_request_id"])
    return deposit


# ─── Resolving a result (shared by the webhook view AND the status-query fallback) ──

@transaction.atomic
def resolve_deposit_result(
    *,
    checkout_request_id: str,
    success: bool,
    mpesa_receipt_number: str = "",
    failure_reason: str = "",
) -> Deposit | None:
    """
    Single source of truth for turning a BluePay result into a final
    deposit state. Idempotent via select_for_update() + the status
    check below -- safe to call from both the webhook and the status
    poll fallback without ever double-crediting a wallet.
    """
    try:
        deposit = Deposit.objects.select_for_update().get(
            checkout_request_id=checkout_request_id, method=Deposit.METHOD_BLUEPAY,
        )
    except Deposit.DoesNotExist:
        return None

    if deposit.status != Deposit.STATUS_PROCESSING:
        return deposit  # already resolved -- nothing to do

    if success:
        deposit.status = Deposit.STATUS_APPROVED
        deposit.result_code = 0
        deposit.result_desc = "Completed via BluePay"
        if mpesa_receipt_number:
            deposit.mpesa_receipt_number = mpesa_receipt_number

        wallet = getattr(deposit.user, "wallet", None)
        if wallet is not None:
            wallet.deposit_balance = wallet.deposit_balance + deposit.amount
            wallet.save(update_fields=["deposit_balance", "updated_at"])
    else:
        deposit.status = Deposit.STATUS_FAILED
        deposit.result_code = 1
        deposit.result_desc = (failure_reason or "Payment failed")[:255]

    deposit.callback_received_at = timezone.now()
    deposit.reviewed_at = timezone.now()
    deposit.save(update_fields=[
        "status", "result_code", "result_desc", "callback_received_at",
        "reviewed_at", "mpesa_receipt_number",
    ])

    from notifications.services import notify_deposit_decision, notify_mpesa_deposit_failed
    try:
        if deposit.status == Deposit.STATUS_APPROVED:
            notify_deposit_decision(deposit, approved=True)
        else:
            notify_mpesa_deposit_failed(deposit)
    except Exception:
        pass

    from .deposit_events import broadcast_deposit_update
    broadcast_deposit_update(deposit)

    return deposit