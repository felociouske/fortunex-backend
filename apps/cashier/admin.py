from django.contrib import admin
from .models import Deposit, Withdrawal


@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    search_fields = ["user__email", "status"]
    list_display = ["user", "amount", "currency", "status", "created_at"]
    list_filter = ["status", "currency"]


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    search_fields = ["user__email", "status"]
    list_display = ["user", "amount", "currency", "status", "created_at"]
    list_filter = ["status", "currency"]
