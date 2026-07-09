from decimal import Decimal

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status

from . import mpesa_service
from .models import Deposit, Withdrawal
from .serializers import DepositSerializer, WithdrawalSerializer, StkPushSerializer, ManualMpesaDepositSerializer


class DepositView(APIView):
    """The original manual/admin-reviewed deposit path -- unchanged, kept
    for anyone not paying via M-Pesa yet (bank wire reference, etc.)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DepositSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class WithdrawalView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = WithdrawalSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class StkPushView(APIView):
    """POST /api/v1/cashier/mpesa/stkpush/ -- initiate an STK push deposit."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = StkPushSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        amount = serializer.validated_data["amount"]
        phone_number = serializer.validated_data["phone_number"]

        # Anti-spam guard: don't let a user fire a second push while one
        # is already in flight (they'd get two PIN prompts on their phone).
        if Deposit.objects.filter(
            user=request.user, status=Deposit.STATUS_PROCESSING, method=Deposit.METHOD_MPESA
        ).exists():
            return Response(
                {"detail": "You already have a deposit request in progress. Please complete it or wait a moment before retrying."},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            deposit = mpesa_service.initiate_deposit(user=request.user, usd_amount=amount, phone_number=phone_number)
        except mpesa_service.MpesaError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({
            "deposit_id": deposit.id,
            "checkout_request_id": deposit.checkout_request_id,
            "kes_amount": str(deposit.kes_amount),
            "detail": "Check your phone and enter your M-Pesa PIN to complete the payment.",
        }, status=status.HTTP_202_ACCEPTED)


class MpesaCallbackView(APIView):
    """
    POST /api/v1/cashier/mpesa/callback/ -- Safaricom calls this once the
    user completes, cancels, or ignores the STK push prompt.

    No auth: Safaricom's servers can't present a JWT, and Daraja doesn't
    support signing callbacks by default. Treat this URL as sensitive
    infrastructure (don't link it anywhere in the frontend).
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        body = request.data.get("Body", {})
        callback = body.get("stkCallback", {})
        checkout_request_id = callback.get("CheckoutRequestID")
        result_code = callback.get("ResultCode")
        result_desc = callback.get("ResultDesc", "")

        if not checkout_request_id or result_code is None:
            # Malformed payload -- still ack with 200 so Safaricom stops
            # retrying. In production, log this payload for investigation.
            return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

        receipt = ""
        if result_code == 0:
            items = callback.get("CallbackMetadata", {}).get("Item", [])
            meta = {i.get("Name"): i.get("Value") for i in items}
            receipt = str(meta.get("MpesaReceiptNumber", ""))

        mpesa_service.resolve_deposit_result(
            checkout_request_id=checkout_request_id,
            result_code=result_code,
            result_desc=result_desc,
            mpesa_receipt_number=receipt,
        )

        # Safaricom only needs this exact 200 response shape to stop
        # retrying -- it does NOT reflect whether the wallet was credited.
        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})


class DepositStatusView(APIView):
    """
    GET /api/v1/cashier/mpesa/status/<checkout_request_id>/

    One-shot fallback if the WebSocket push doesn't arrive in time --
    NOT meant to be polled on an interval. If still PROCESSING, actively
    re-asks Daraja instead of just re-reading our own (possibly stale,
    if the callback never arrived) row.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, checkout_request_id):
        try:
            deposit = Deposit.objects.get(checkout_request_id=checkout_request_id, user=request.user)
        except Deposit.DoesNotExist:
            return Response({"detail": "Deposit not found."}, status=status.HTTP_404_NOT_FOUND)

        if deposit.status == Deposit.STATUS_PROCESSING:
            try:
                data = mpesa_service.query_stk_status(checkout_request_id)
                # A genuinely-still-pending push comes back WITHOUT a
                # ResultCode key (Daraja wraps it as errorCode
                # "500.001.1001" instead) -- only resolve if it's present.
                if "ResultCode" in data:
                    mpesa_service.resolve_deposit_result(
                        checkout_request_id=checkout_request_id,
                        result_code=int(data.get("ResultCode", -1)),
                        result_desc=data.get("ResultDesc", ""),
                    )
                    deposit.refresh_from_db()
            except mpesa_service.MpesaError:
                pass  # keep returning the last known (PROCESSING) state

        return Response({
            "id": deposit.id,
            "status": deposit.status,
            "amount": str(deposit.amount),
            "kes_amount": str(deposit.kes_amount) if deposit.kes_amount else None,
            "mpesa_receipt_number": deposit.mpesa_receipt_number,
            "result_desc": deposit.result_desc,
        })


class ExchangeRateView(APIView):
    """
    GET /api/v1/cashier/exchange-rate/
    Single source of truth for both the USD->KES rate AND the paybill
    details needed to render manual-deposit payment instructions --
    so the frontend never hardcodes the shortcode either.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "usd_to_kes": settings.USD_TO_KES_RATE,
            "paybill_shortcode": settings.MPESA_SHORTCODE,
            "paybill_account_name": "FortuneX",
        })


class ManualMpesaDepositView(APIView):
    """
    POST /api/v1/cashier/mpesa/manual/
    User paid via the Paybill directly and is submitting proof (the
    M-Pesa code + the phone they paid from) for admin review. Creates
    a normal PENDING Deposit -- your existing DepositAdmin approve/
    reject actions handle everything from here, unchanged.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ManualMpesaDepositSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        amount = serializer.validated_data["amount"]
        kes_amount = mpesa_service.usd_to_kes(amount)

        deposit = Deposit.objects.create(
            user=request.user,
            amount=amount,
            currency="USD",
            status=Deposit.STATUS_PENDING,
            method=Deposit.METHOD_MANUAL_MPESA,
            phone_number=serializer.validated_data["phone_number"],
            kes_amount=kes_amount,
            exchange_rate=Decimal(str(settings.USD_TO_KES_RATE)),
            mpesa_receipt_number=serializer.validated_data["mpesa_code"],
        )

        return Response({
            "id": deposit.id,
            "detail": "Submitted for verification. You'll be notified once it's approved.",
        }, status=status.HTTP_201_CREATED)


class TransactionsView(APIView):
    """
    GET /api/v1/cashier/transactions/
    Unified deposit + withdrawal history for the authenticated user,
    normalized into one shape with a "type" discriminator and sorted
    newest-first. Built as plain dicts here rather than a serializer
    since Deposit and Withdrawal have genuinely different fields --
    forcing them through one ModelSerializer would mean a pile of
    nullable fields that don't apply to the other type.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        deposits = [
            {
                "id": f"D{d.id}",
                "type": "DEPOSIT",
                "amount": str(d.amount),
                "currency": d.currency,
                "method": d.get_method_display(),
                "detail": d.mpesa_receipt_number or (f"KES {d.kes_amount}" if d.kes_amount else "-"),
                "status": d.status,
                "created_at": d.created_at,
            }
            for d in request.user.deposits.all()
        ]
        withdrawals = [
            {
                "id": f"W{w.id}",
                "type": "WITHDRAWAL",
                "amount": str(w.amount),
                "currency": w.currency,
                "method": w.get_source_wallet_display(),
                "detail": w.payout_details or "-",
                "status": w.status,
                "created_at": w.created_at,
            }
            for w in request.user.withdrawals.all()
        ]

        transactions = sorted(deposits + withdrawals, key=lambda t: t["created_at"], reverse=True)
        return Response({"transactions": transactions})


