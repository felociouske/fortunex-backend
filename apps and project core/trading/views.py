from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MarketInstrument, Tick, TradePosition, BotRun
from .serializers import (
    MarketInstrumentSerializer,
    OpenContractSerializer,
    TickSerializer,
    TradePositionSerializer,
    BotRunSerializer,
    StartBotRunSerializer,
)
from .win_chance import resolve_active_tier
from .wallet_utils import debit_stake, check_stake_affordable, InsufficientFunds
from .position_events import broadcast_position_opened
from bots.services import get_active_automation
from bots.models import AutomationProduct

class MarketListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        instruments = MarketInstrument.objects.filter(active=True)
        serializer = MarketInstrumentSerializer(instruments, many=True)
        return Response(serializer.data)


class InstrumentTicksView(APIView):
    """
    GET /trading/instruments/<symbol>/ticks/?limit=100
    Recent price history for one instrument -- used to seed the chart
    with history on page load, before live ticks start arriving over
    the WebSocket.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, symbol):
        try:
            instrument = MarketInstrument.objects.get(symbol=symbol, active=True)
        except MarketInstrument.DoesNotExist:
            return Response({"detail": "Instrument not found."}, status=status.HTTP_404_NOT_FOUND)

        limit = min(int(request.query_params.get("limit", 100)), 500)
        ticks = Tick.objects.filter(instrument=instrument).order_by("-tick_count")[:limit]
        serializer = TickSerializer(reversed(list(ticks)), many=True)
        return Response(serializer.data)


class OpenPositionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        positions = TradePosition.objects.filter(
            user=request.user, status=TradePosition.STATUS_OPEN
        ).select_related("instrument")
        serializer = TradePositionSerializer(positions, many=True)
        return Response(serializer.data)


class PositionHistoryView(APIView):
    """GET /trading/positions/history/ -- settled (won/lost) contracts, most recent first."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        positions = TradePosition.objects.filter(
            user=request.user
        ).exclude(status=TradePosition.STATUS_OPEN).select_related("instrument").order_by("-closed_at")[:50]
        serializer = TradePositionSerializer(positions, many=True)
        return Response(serializer.data)


class MyTierView(APIView):
    """
    GET /trading/my-tier/
    The authenticated user's currently active win-chance tier and which
    contract types they have unlocked -- used by the frontend to render
    the contract picker (greying out locked types) and the AI advisory
    banner (only shown when an AI is the active automation).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tier = resolve_active_tier(request.user)
        automation = get_active_automation(request.user)

        return Response({
            "win_chance": tier.win_chance,
            "win_chance_percent": tier.win_chance * 100,
            "unlocked_contracts": tier.unlocked_contracts,
            "source_label": tier.source_label,
            "active_automation": (
                {
                    "id": automation.id,
                    "kind": automation.product.kind,
                    "name": automation.product.name,
                    "tier": automation.product.tier,
                }
                if automation else None
            ),
        })


class OpenContractView(APIView):
    """
    POST /trading/contracts/
    Opens a new contract of any supported type: validates the request
    (including KYC verification and combined real+deposit balance
    affordability -- see OpenContractSerializer), debits the stake
    (real_balance first, deposit_balance for any remainder -- see
    wallet_utils.debit_stake), resolves the user's current active
    win-chance tier and locks it onto the contract, and creates the
    OPEN TradePosition. Settlement happens later, asynchronously, by
    the price engine once the contract's duration elapses.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = OpenContractSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        instrument = serializer._instrument

        latest_tick = Tick.objects.filter(instrument=instrument).order_by("-tick_count").first()
        if latest_tick is None:
            return Response(
                {"detail": "No live price available for this instrument yet. Try again shortly."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        tier = resolve_active_tier(request.user)

        with transaction.atomic():
            wallet = request.user.wallet.__class__.objects.select_for_update().get(user=request.user)
            try:
                debit_stake(wallet, data["stake"])
            except InsufficientFunds as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            wallet.save(update_fields=["real_balance", "deposit_balance", "updated_at"])

            position = TradePosition.objects.create(
                user=request.user,
                instrument=instrument,
                contract_type=data["contract_type"],
                side=data.get("side", ""),
                prediction=data.get("prediction") or {},
                duration_unit=data["duration_unit"],
                duration_value=data["duration_value"],
                stake=data["stake"],
                entry_price=latest_tick.price,
                current_price=latest_tick.price,
                entry_tick_count=latest_tick.tick_count,
                win_chance_applied=Decimal(str(tier.win_chance)),
                win_chance_source=tier.source_label,
                expires_at=(
                    timezone.now() + timezone.timedelta(seconds=data["duration_value"])
                    if data["duration_unit"] == TradePosition.DURATION_SECONDS
                    else None
                ),
            )


        # Broadcast AFTER the transaction commits, so any listener that
        # refetches the open-positions list in response sees the row.
        broadcast_position_opened(position)

        return Response(TradePositionSerializer(position).data, status=status.HTTP_201_CREATED)


class StartBotRunView(APIView):
    """
    POST /trading/botrun/start/
    Starts a bot-automation run: freezes a contract config + stake +
    stop-loss + take-profit, opens the first contract immediately, and
    lets the price engine's settlement loop keep opening the next one
    automatically until a stop condition is hit. Only available when
    the user's active automation is a BOT (kind=BOT) -- AIs never
    auto-submit trades, per product decision.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        automation = get_active_automation(request.user)
        if automation is None or automation.product.kind != AutomationProduct.KIND_BOT:
            return Response(
                {"detail": "You need an active trading bot to start automation."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = StartBotRunSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        instrument = serializer._instrument

        latest_tick = Tick.objects.filter(instrument=instrument).order_by("-tick_count").first()
        if latest_tick is None:
            return Response(
                {"detail": "No live price available for this instrument yet. Try again shortly."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        tier = resolve_active_tier(request.user)

        with transaction.atomic():
            wallet = request.user.wallet.__class__.objects.select_for_update().get(user=request.user)
            try:
                debit_stake(wallet, data["stake"])
            except InsufficientFunds as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            wallet.save(update_fields=["real_balance", "deposit_balance", "updated_at"])

            first_position = TradePosition.objects.create(
                user=request.user,
                instrument=instrument,
                contract_type=data["contract_type"],
                side=data.get("side", ""),
                prediction=data.get("prediction") or {},
                duration_unit=data["duration_unit"],
                duration_value=data["duration_value"],
                stake=data["stake"],
                entry_price=latest_tick.price,
                current_price=latest_tick.price,
                entry_tick_count=latest_tick.tick_count,
                win_chance_applied=Decimal(str(tier.win_chance)),
                win_chance_source=tier.source_label,
                expires_at=(
                    timezone.now() + timezone.timedelta(seconds=data["duration_value"])
                    if data["duration_unit"] == TradePosition.DURATION_SECONDS
                    else None
                ),
            )

            run = BotRun.objects.create(
                user=request.user,
                instrument=instrument,
                contract_type=data["contract_type"],
                side=data.get("side", ""),
                prediction=data.get("prediction") or {},
                duration_unit=data["duration_unit"],
                duration_value=data["duration_value"],
                stake=data["stake"],
                stop_loss=data["stop_loss"],
                take_profit=data["take_profit"],
                current_position=first_position,
            )

        # Broadcast AFTER the transaction commits.
        broadcast_position_opened(first_position)

        return Response(BotRunSerializer(run).data, status=status.HTTP_201_CREATED)


class StopBotRunView(APIView):
    """
    POST /trading/botrun/stop/
    Stops the user's currently running bot run. The contract it's
    currently waiting on (if any) is left to settle normally -- it is
    NOT cancelled early, since a contract once opened follows the same
    rules as any manually-placed one. Stopping just prevents the NEXT
    contract from being opened once the current one settles.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        run = BotRun.objects.filter(user=request.user, status=BotRun.STATUS_RUNNING).first()
        if run is None:
            return Response({"detail": "No running bot automation found."}, status=status.HTTP_404_NOT_FOUND)

        run.status = BotRun.STATUS_STOPPED_MANUAL
        run.stopped_at = timezone.now()
        run.save(update_fields=["status", "stopped_at"])

        return Response(BotRunSerializer(run).data)


class MyBotRunView(APIView):
    """GET /trading/botrun/mine/ -- the user's currently running bot automation, if any, plus recent history."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        current = BotRun.objects.filter(
            user=request.user, status=BotRun.STATUS_RUNNING
        ).select_related("instrument").first()
        history = BotRun.objects.filter(
            user=request.user
        ).exclude(status=BotRun.STATUS_RUNNING).select_related("instrument")[:20]

        return Response({
            "current": BotRunSerializer(current).data if current else None,
            "history": BotRunSerializer(history, many=True).data,
        })