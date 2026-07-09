from django.contrib import admin
from .models import AutomationProduct, UserAutomation


@admin.register(AutomationProduct)
class AutomationProductAdmin(admin.ModelAdmin):
    search_fields = ["name", "kind"]
    list_display = [
        "name", "kind", "tier", "price", "win_chance",
        "unlocked_contract_count", "commission_rate", "active",
    ]
    list_filter = ["kind", "active"]
    ordering = ["kind", "tier"]


@admin.register(UserAutomation)
class UserAutomationAdmin(admin.ModelAdmin):
    search_fields = ["user__email", "product__name"]
    list_display = ["user", "product", "active", "purchased_at", "deactivated_at"]
    list_filter = ["active", "product__kind"]