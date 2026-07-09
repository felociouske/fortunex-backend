from django.contrib import admin
from .models import MarketItem


@admin.register(MarketItem)
class MarketItemAdmin(admin.ModelAdmin):
    search_fields = ["name", "category", "tags"]
    list_display = ["name", "category", "price", "active"]
    list_filter = ["active", "category"]
