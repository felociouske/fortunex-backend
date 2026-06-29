# Django admin — register User and Wallet for admin panel management
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Wallet


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Extended admin for the custom User model.
    Adds KYC fields and referral info to the standard user admin.
    """
    list_display  = ["email", "first_name", "last_name", "country", "kyc_status", "date_joined"]
    list_filter   = ["kyc_status", "country", "is_active", "is_staff"]
    search_fields = ["email", "first_name", "last_name", "referral_code"]
    ordering      = ["-date_joined"]

    # Sections shown when viewing a specific user
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Profile", {"fields": ("date_of_birth", "country", "phone_number")}),
        ("KYC",     {"fields": ("kyc_status", "kyc_document", "kyc_submitted_at",
                                "kyc_reviewed_at", "kyc_notes")}),
        ("Referral",{"fields": ("referral_code", "referred_by")}),
    )
    readonly_fields = ["kyc_submitted_at", "kyc_reviewed_at", "referral_code"]


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    """Read-only wallet view in admin — balances are updated programmatically."""
    list_display  = ["user", "real_balance", "deposit_balance", "yield_balance", "currency", "updated_at"]
    search_fields = ["user__email"]
    readonly_fields = ["real_balance", "deposit_balance", "yield_balance", "updated_at"]
