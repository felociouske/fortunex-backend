# Django admin — User, Wallet, KYCSubmission, with inlines so an admin
# can see everything about a user (wallet, referrals, submitted KYC
# documents) from one page instead of hopping between models.
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils import timezone
from django.utils.safestring import mark_safe
from .models import User, Wallet, KYCSubmission


class WalletInline(admin.StackedInline):
    """Editable balances directly on the User page -- no need to hop to
    the separate Wallet admin for routine balance corrections."""
    model = Wallet
    extra = 0
    can_delete = False


class KYCSubmissionInline(admin.TabularInline):
    """
    Read-only view of everything this user has submitted for KYC,
    right on their own admin page -- including a clickable image
    thumbnail, so you don't have to open each KYCSubmission separately
    just to see what was uploaded.
    """
    model = KYCSubmission
    extra = 0
    can_delete = False
    fields = ["category", "status", "document_type", "documents_preview", "submitted_at", "reviewed_at"]
    readonly_fields = ["category", "status", "document_type", "documents_preview", "submitted_at", "reviewed_at"]

    def documents_preview(self, obj):
        images = [
            (label, f.url) for label, f in
            [("Front", obj.front_image), ("Back", obj.back_image), ("Address", obj.address_image)]
            if f
        ]
        if not images:
            return "-"
        thumbs = "".join(
            f'<a href="{url}" target="_blank" style="margin-right:8px;">'
            f'<img src="{url}" style="height:50px;border-radius:4px;border:1px solid #444;" title="{label}" />'
            f'</a>'
            for label, url in images
        )
        return mark_safe(thumbs)
    documents_preview.short_description = "Documents"

    def has_add_permission(self, request, obj=None):
        return False  # submissions only come from the user themselves, via the API


class ReferralsInline(admin.TabularInline):
    """
    Everyone this user has personally invited -- self-referential FK
    (User.referred_by points back at User), so fk_name is required to
    tell Django which side of the relationship this inline represents.
    """
    model = User
    fk_name = "referred_by"
    verbose_name = "Referral"
    verbose_name_plural = "Users invited by this person"
    extra = 0
    can_delete = False
    fields = ["email", "full_name", "kyc_status", "date_joined"]
    readonly_fields = ["email", "full_name", "kyc_status", "date_joined"]

    def full_name(self, obj):
        return obj.full_name

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["email", "first_name", "last_name", "country", "kyc_status", "referrals_count", "date_joined"]
    list_filter = ["kyc_status", "country", "is_active", "is_staff"]
    search_fields = ["email", "first_name", "last_name", "referral_code", "kra_pin"]
    ordering = ["-date_joined"]
    inlines = [WalletInline, KYCSubmissionInline, ReferralsInline]
    actions = ["verify_kyc_fully"]

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Profile", {"fields": ("date_of_birth", "country", "phone_number", "location", "kra_pin")}),
        ("KYC",     {"fields": ("kyc_status",)}),
        ("Referral",{"fields": ("referral_code", "referred_by")}),
    )
    readonly_fields = ["referral_code"]

    def referrals_count(self, obj):
        return obj.referrals.count()
    referrals_count.short_description = "Referrals"

    @admin.action(description="Verify KYC completely (approves Identity + Address, sets account VERIFIED)")
    def verify_kyc_fully(self, request, queryset):
        """
        "Approve KYC at a go" -- one click verifies both live categories
        for every selected user and flips their overall status, instead
        of opening each user, then each KYCSubmission, one at a time.
        """
        verified_count = 0
        for user in queryset:
            submissions = user.kyc_submissions.filter(
                category__in=[KYCSubmission.CATEGORY_IDENTITY, KYCSubmission.CATEGORY_ADDRESS]
            )
            if submissions.count() < 2:
                continue  # hasn't submitted both categories yet -- nothing to approve
            submissions.update(status=KYCSubmission.STATUS_VERIFIED, reviewed_at=timezone.now())
            user.kyc_status = User.KYC_VERIFIED
            user.save(update_fields=["kyc_status"])
            verified_count += 1

        skipped = queryset.count() - verified_count
        msg = f"Fully verified {verified_count} user(s)."
        if skipped:
            msg += f" Skipped {skipped} -- they haven't submitted both Identity and Address yet."
        self.message_user(request, msg)


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ["user", "real_balance", "deposit_balance", "yield_balance", "currency", "updated_at"]
    search_fields = ["user__email"]
    readonly_fields = ["real_balance", "deposit_balance", "yield_balance", "updated_at"]


@admin.register(KYCSubmission)
class KYCSubmissionAdmin(admin.ModelAdmin):
    list_display = ["user", "category", "status", "document_type", "submitted_at", "reviewed_at"]
    list_filter = ["category", "status", "document_type"]
    search_fields = ["user__email"]
    readonly_fields = ["submitted_at", "documents_preview"]
    date_hierarchy = "submitted_at"
    actions = ["approve_submissions", "reject_submissions"]

    fields = [
        "user", "category", "status", "document_type",
        "front_image", "back_image", "address_image", "documents_preview",
        "latitude", "longitude", "submitted_at", "reviewed_at", "review_notes",
    ]

    def documents_preview(self, obj):
        images = [
            (label, f.url) for label, f in
            [("Front", obj.front_image), ("Back", obj.back_image), ("Address", obj.address_image)]
            if f
        ]
        if not images:
            return "-"
        thumbs = "".join(
            f'<a href="{url}" target="_blank" style="margin-right:10px;">'
            f'<img src="{url}" style="height:120px;border-radius:6px;border:1px solid #444;" title="{label}" />'
            f'</a>'
            for label, url in images
        )
        return mark_safe(thumbs)
    documents_preview.short_description = "Submitted documents"

    @admin.action(description="Approve selected KYC submissions")
    def approve_submissions(self, request, queryset):
        for submission in queryset:
            submission.status = KYCSubmission.STATUS_VERIFIED
            submission.reviewed_at = timezone.now()
            submission.save(update_fields=["status", "reviewed_at"])
            self._maybe_verify_user(submission.user)
        self.message_user(request, f"{queryset.count()} submission(s) approved.")

    @admin.action(description="Reject selected KYC submissions")
    def reject_submissions(self, request, queryset):
        queryset.update(status=KYCSubmission.STATUS_REJECTED, reviewed_at=timezone.now())
        self.message_user(request, f"{queryset.count()} submission(s) rejected.")

    def _maybe_verify_user(self, user):
        categories = {
            s.category: s.status
            for s in user.kyc_submissions.filter(
                category__in=[KYCSubmission.CATEGORY_IDENTITY, KYCSubmission.CATEGORY_ADDRESS]
            )
        }
        both_verified = (
            categories.get(KYCSubmission.CATEGORY_IDENTITY) == KYCSubmission.STATUS_VERIFIED
            and categories.get(KYCSubmission.CATEGORY_ADDRESS) == KYCSubmission.STATUS_VERIFIED
        )
        if both_verified and user.kyc_status != User.KYC_VERIFIED:
            user.kyc_status = User.KYC_VERIFIED
            user.save(update_fields=["kyc_status"])