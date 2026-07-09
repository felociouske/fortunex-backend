"""
M-Pesa Daraja (Lipa Na M-Pesa Online / STK Push) integration.

This module owns three things:
  1. Talking to Safaricom's Daraja API (OAuth token, STK push, status query).
  2. The USD<->KES conversion at the boundary between our USD wallets
     and Daraja's KES-only API.
  3. Turning a Daraja result -- from EITHER the async callback or the
     status-query fallback -- into a credited wallet + notification +
     WebSocket push, written ONCE (resolve_deposit_result) so the two
     call sites can never drift apart or double-credit a wallet.
"""
from __future__ import annotations

import base64
import re
from decimal import Decimal, ROUND_HALF_UP

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Deposit


# ─── Phone number handling ───────────────────────────────────────────────────

def normalize_phone(raw: str) -> str | None:
    """
    Accepts the common formats a Kenyan user might type and normalizes
    to Daraja's required 2547XXXXXXXX / 2541XXXXXXXX (12 digits, no '+').
    Returns None if it doesn't look like a valid Safaricom-format number.
    """
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)  # strip spaces, +, dashes, etc.

    if digits.startswith("0") and len(digits) == 10:      # 0712345678
        digits = "254" + digits[1:]
    elif digits.startswith("7") and len(digits) == 9:      # 712345678
        digits = "254" + digits
    elif digits.startswith("1") and len(digits) == 9:      # 112345678 (Safaricom's newer 01xx range)
        digits = "254" + digits
    elif digits.startswith("254") and len(digits) == 12:   # already normalized
        pass
    else:
        return None

    # Final shape check: 2547XXXXXXXX or 2541XXXXXXXX, exactly 12 digits.
    if not re.fullmatch(r"254[71]\d{8}", digits):
        return None
    return digits


# ─── Currency conversion ─────────────────────────────────────────────────────

def usd_to_kes(usd_amount: Decimal) -> Decimal:
    """Whole-shilling KES amount to send to Daraja -- STK push rejects decimals."""
    rate = Decimal(str(settings.USD_TO_KES_RATE))
    return (Decimal(usd_amount) * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


# ─── Daraja OAuth + STK push ──────────────────────────────────────────────────

class MpesaError(Exception):
    """Raised for any Daraja-side failure: auth, network, or a rejected request."""


def _get_access_token() -> str:
    url = f"{settings.MPESA_BASE_URL}/oauth/v1/generate?grant_type=client_credentials"
    try:
        resp = requests.get(
            url,
            auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET),
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise MpesaError(f"Could not reach Safaricom (auth): {exc}") from exc

    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise MpesaError(f"Safaricom auth response missing access_token: {data}")
    return token


def _stk_password_and_timestamp() -> tuple[str, str]:
    # Daraja's password is base64(Shortcode + Passkey + Timestamp),
    # and the timestamp itself must match the format below exactly.
    timestamp = timezone.localtime().strftime("%Y%m%d%H%M%S")
    raw = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}"
    password = base64.b64encode(raw.encode()).decode()
    return password, timestamp


def send_stk_push(*, phone_number: str, kes_amount: Decimal, account_reference: str, description: str) -> dict:
    """Fires the STK push. Returns Safaricom's JSON on success; raises MpesaError otherwise."""
    token = _get_access_token()
    password, timestamp = _stk_password_and_timestamp()

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(kes_amount),  # Daraja requires a whole number, no decimals
        "PartyA": phone_number,
        "PartyB": settings.MPESA_SHORTCODE,
        "PhoneNumber": phone_number,
        "CallBackURL": settings.MPESA_CALLBACK_URL,
        "AccountReference": account_reference[:12],  # Daraja hard-caps this at 12 chars
        "TransactionDesc": description[:13],          # ...and this at 13 chars
    }

    try:
        resp = requests.post(
            f"{settings.MPESA_BASE_URL}/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
        data = resp.json()
    except requests.RequestException as exc:
        raise MpesaError(f"Could not reach Safaricom (STK push): {exc}") from exc
    except ValueError as exc:
        raise MpesaError(f"Safaricom returned a non-JSON response: {resp.text[:200]}") from exc

    if data.get("ResponseCode") != "0":
        # e.g. bad shortcode/passkey, malformed phone number, etc.
        raise MpesaError(data.get("errorMessage") or data.get("ResponseDescription") or str(data))

    return data


def query_stk_status(checkout_request_id: str) -> dict:
    """Explicit status query -- used only as a fallback if the async callback never arrives."""
    token = _get_access_token()
    password, timestamp = _stk_password_and_timestamp()

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "CheckoutRequestID": checkout_request_id,
    }
    try:
        resp = requests.post(
            f"{settings.MPESA_BASE_URL}/mpesa/stkpushquery/v1/query",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise MpesaError(f"Could not query STK status: {exc}") from exc


# ─── Initiating a deposit ─────────────────────────────────────────────────────

def initiate_deposit(*, user, usd_amount: Decimal, phone_number: str) -> Deposit:
    """
    Creates the Deposit row FIRST (status=PROCESSING) so there's always
    something to look up, even if the STK push call fails partway through.
    """
    kes_amount = usd_to_kes(usd_amount)

    deposit = Deposit.objects.create(
        user=user,
        amount=usd_amount,
        currency="USD",
        status=Deposit.STATUS_PROCESSING,
        method=Deposit.METHOD_MPESA,
        phone_number=phone_number,
        kes_amount=kes_amount,
        exchange_rate=Decimal(str(settings.USD_TO_KES_RATE)),
    )

    try:
        data = send_stk_push(
            phone_number=phone_number,
            kes_amount=kes_amount,
            account_reference=f"FX{deposit.id}",
            description="Fortunex deposit",
        )
    except MpesaError as exc:
        deposit.status = Deposit.STATUS_FAILED
        deposit.result_desc = str(exc)[:255]
        deposit.reviewed_at = timezone.now()
        deposit.save(update_fields=["status", "result_desc", "reviewed_at"])
        raise

    deposit.merchant_request_id = data.get("MerchantRequestID", "")
    deposit.checkout_request_id = data.get("CheckoutRequestID", "")
    deposit.save(update_fields=["merchant_request_id", "checkout_request_id"])
    return deposit


# ─── Resolving a result (shared by the callback view AND the status-query fallback) ──

@transaction.atomic
def resolve_deposit_result(*, checkout_request_id: str, result_code: int, result_desc: str,
                            mpesa_receipt_number: str = "") -> Deposit | None:
    """
    Single source of truth for turning a Daraja result into a final
    deposit state. Idempotent: select_for_update() + the status check
    below mean that if the callback AND the fallback query both
    eventually resolve the same deposit, the second call is a no-op --
    it can never double-credit the wallet.
    """
    try:
        deposit = Deposit.objects.select_for_update().get(checkout_request_id=checkout_request_id)
    except Deposit.DoesNotExist:
        return None

    if deposit.status != Deposit.STATUS_PROCESSING:
        return deposit  # already resolved by the other call site -- nothing to do

    deposit.result_code = result_code
    deposit.result_desc = result_desc[:255]
    deposit.callback_received_at = timezone.now()
    deposit.reviewed_at = timezone.now()

    if result_code == 0:
        deposit.status = Deposit.STATUS_APPROVED
        deposit.mpesa_receipt_number = mpesa_receipt_number

        # Auto-credit, per your instruction -- no admin step for M-Pesa.
        wallet = getattr(deposit.user, "wallet", None)
        if wallet is not None:
            wallet.deposit_balance = wallet.deposit_balance + deposit.amount
            wallet.save(update_fields=["deposit_balance", "updated_at"])
    else:
        deposit.status = Deposit.STATUS_FAILED

    deposit.save(update_fields=[
        "status", "result_code", "result_desc", "callback_received_at",
        "reviewed_at", "mpesa_receipt_number",
    ])

    # Notification + live WebSocket push are both best-effort -- a
    # failure here must never roll back the wallet credit above.
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