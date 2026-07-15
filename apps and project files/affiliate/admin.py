from django.contrib import admin
from .models import ReferralLink, ReferralCommission


@admin.register(ReferralLink)
class ReferralLinkAdmin(admin.ModelAdmin):
    list_display = ["user", "code", "created_at"]
    search_fields = ["user__email", "code"]
    readonly_fields = ["code", "created_at"]


@admin.register(ReferralCommission)
class ReferralCommissionAdmin(admin.ModelAdmin):
    list_display = ["referrer", "referred", "amount", "description", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["referrer__email", "referred__email"]
    date_hierarchy = "created_at"
    readonly_fields = ["referrer", "referred", "amount", "description", "created_at"]

    def has_add_permission(self, request):
        return False  # commissions are only ever created by your trading/settlement logic, never by hand