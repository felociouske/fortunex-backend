import json

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status

from . import bluepay_service
from .models import Deposit
from .bluepay_serializers import BluePayStkPushSerializer


class BluePayStkPushView(APIView):
    """POST /api/v1/cashier/bluepay/stkpush/ -- initiate a BluePay M-Pesa STK push deposit."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = BluePayStkPushSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        amount = serializer.validated_data["amount"]
        phone_number = serializer.validated_data["phone_number"]

        # Anti-spam guard, same pattern as the Daraja flow: don't let a
        # user fire a second push while one is already in flight.
        if Deposit.objects.filter(
            user=request.user, status=Deposit.STATUS_PROCESSING, method=Deposit.METHOD_BLUEPAY
        ).exists():
            return Response(
                {"detail": "You already have a deposit request in progress. Please complete it or wait a moment before retrying."},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            deposit = bluepay_service.initiate_deposit(user=request.user, usd_amount=amount, phone_number=phone_number)
        except bluepay_service.BluePayError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({
            "deposit_id": deposit.id,
            "checkout_request_id": deposit.checkout_request_id,
            "kes_amount": str(deposit.kes_amount),
            "detail": "Check your phone and enter your M-Pesa PIN to complete the payment.",
        }, status=status.HTTP_202_ACCEPTED)


class BluePayWebhookView(APIView):
    """
    POST /api/v1/cashier/bluepay/webhook/

    Set this exact URL as your Account -> Callback URL in the BluePay
    dashboard (dashboard-level callback, applies to all payments).

    No JWT auth -- BluePay can't present one. Instead every webhook
    carries an `X-BluePay-Signature: v1=<hmac-sha256 hex>` header,
    computed over the RAW request body using your API secret. We
    verify that before trusting anything in the payload, and read
    request.body BEFORE touching request.data so the raw bytes used
    for verification are guaranteed to match exactly what BluePay signed.

    If the signature check ever mismatches for a legitimate payload
    (e.g. you rotate BLUEPAY_API_SECRET), deposits simply stay in
    PROCESSING and get resolved by the status-poll fallback instead --
    this endpoint fails closed, not crashed.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        raw_body = request.body  # must read first, before any .data access
        signature = request.headers.get("X-BluePay-Signature", "")

        if not bluepay_service.verify_webhook_signature(raw_body=raw_body, signature_header=signature):
            return Response({"detail": "Invalid signature."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return Response({"detail": "Invalid JSON."}, status=status.HTTP_400_BAD_REQUEST)

        event = payload.get("event", "")
        data = payload.get("data") or {}
        checkout_request_id = data.get("checkout_request_id")

        # Only collection (deposit) events are wired up -- B2C/wallet
        # top-up events are ignored on purpose (out of scope for now).
        if event not in ("mpesa.payment.received", "mpesa.payment.failed") or not checkout_request_id:
            return Response({"detail": "Accepted"})

        success = event == "mpesa.payment.received" and data.get("status") == "success"

        bluepay_service.resolve_deposit_result(
            checkout_request_id=checkout_request_id,
            success=success,
            mpesa_receipt_number=data.get("mpesa_receipt_number") or "",
            failure_reason=data.get("message") or data.get("failure_reason") or "",
        )
        return Response({"detail": "Accepted"})


class BluePayDepositStatusView(APIView):
    """
    GET /api/v1/cashier/bluepay/status/<checkout_request_id>/

    One-shot fallback if the webhook doesn't arrive in time -- NOT
    meant to be polled on an interval. If still PROCESSING, actively
    re-asks BluePay instead of just re-reading our own (possibly stale) row.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, checkout_request_id):
        try:
            deposit = Deposit.objects.get(
                checkout_request_id=checkout_request_id, user=request.user, method=Deposit.METHOD_BLUEPAY,
            )
        except Deposit.DoesNotExist:
            return Response({"detail": "Deposit not found."}, status=status.HTTP_404_NOT_FOUND)

        if deposit.status == Deposit.STATUS_PROCESSING:
            try:
                data = bluepay_service.query_status(checkout_request_id=checkout_request_id)
                if data.get("paid"):
                    payment = data.get("payment") or {}
                    bluepay_service.resolve_deposit_result(
                        checkout_request_id=checkout_request_id,
                        success=True,
                        mpesa_receipt_number=payment.get("mpesa_receipt_number") or "",
                    )
                    deposit.refresh_from_db()
                elif data.get("failed"):
                    bluepay_service.resolve_deposit_result(
                        checkout_request_id=checkout_request_id,
                        success=False,
                        failure_reason=data.get("message") or "",
                    )
                    deposit.refresh_from_db()
            except bluepay_service.BluePayError:
                pass  # keep returning the last known (PROCESSING) state

        return Response({
            "id": deposit.id,
            "status": deposit.status,
            "amount": str(deposit.amount),
            "kes_amount": str(deposit.kes_amount) if deposit.kes_amount else None,
            "mpesa_receipt_number": deposit.mpesa_receipt_number,
            "result_desc": deposit.result_desc,
        })