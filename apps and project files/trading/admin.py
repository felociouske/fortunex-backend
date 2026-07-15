from django.contrib import admin
from .models import MarketInstrument, TradePosition, Tick, BotRun


@admin.register(MarketInstrument)
class MarketInstrumentAdmin(admin.ModelAdmin):
    search_fields = ["name", "symbol", "category"]
    list_display = ["name", "symbol", "category", "active", "base_price", "volatility", "tick_interval_ms"]
    list_filter = ["active", "category"]


@admin.register(TradePosition)
class TradePositionAdmin(admin.ModelAdmin):
    search_fields = ["user__email", "instrument__symbol", "status"]
    list_display = [
        "user", "instrument", "contract_type", "side", "status",
        "win_chance_applied", "win_chance_source",
        "opened_at", "closed_at", "stake", "profit_loss",
    ]
    list_filter = ["status", "side", "contract_type", "duration_unit", "win_chance_source"]


@admin.register(Tick)
class TickAdmin(admin.ModelAdmin):
    search_fields = ["instrument__symbol"]
    list_display = ["instrument", "tick_count", "price", "created_at"]
    list_filter = ["instrument"]


@admin.register(BotRun)
class BotRunAdmin(admin.ModelAdmin):
    search_fields = ["user__email", "instrument__symbol"]
    list_display = [
        "user", "instrument", "contract_type", "status",
        "cumulative_profit_loss", "trades_count", "stake",
        "stop_loss", "take_profit", "started_at", "stopped_at",
    ]
    list_filter = ["status", "contract_type"]