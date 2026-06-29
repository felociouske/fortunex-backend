from django.contrib import admin
from .models import MarketInstrument, TradePosition


@admin.register(MarketInstrument)
class MarketInstrumentAdmin(admin.ModelAdmin):
    search_fields = ["name", "symbol", "category"]
    list_display = ["name", "symbol", "category", "active"]
    list_filter = ["active", "category"]


@admin.register(TradePosition)
class TradePositionAdmin(admin.ModelAdmin):
    search_fields = ["user__email", "instrument__symbol", "status"]
    list_display = ["user", "instrument", "side", "status", "opened_at", "stake"]
    list_filter = ["status", "side"]
