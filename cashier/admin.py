from django.contrib import admin
from django.db import transaction
from django.shortcuts import render
from django.utils import timezone

from .models import Deposit, Withdrawal
from .forms import RemarkForm


def _remark_action(self, request, queryset, *, do_action, template_name, description):
    """
    Shared two-step admin action: first call renders a remark-entry
    form (Django's standard pattern for actions needing extra input
    via intermediate pages); the second call (form submitted) runs
    `do_action(request, queryset, remark)` and redirects back to the
    change list.
    """
    if "apply" in request.POST:
        form = RemarkForm(request.POST)
        if form.is_valid():
            remark = form.cleaned_data["remark"]
            do_action(request, queryset, remark)
            return None  # falls through to Django's default "done" redirect
    else:
        form = RemarkForm()

    return render(request, template_name, {
        "items": queryset,
        "form": form,
        "action_description": description,
        "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
    })


@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    search_fields = ["user__email", "status"]
    list_display = ["user", "amount", "currency", "status", "created_at", "reviewed_at"]
    list_filter = ["status", "currency"]
    actions = ["approve_deposits", "reject_deposits"]

    @admin.action(description="Approve selected deposits (credits deposit_balance)")
    def approve_deposits(self, request, queryset):
        def do_approve(request, queryset, remark):
            from notifications.services import notify_deposit_decision
            approved, skipped_no_wallet = 0, 0
            with transaction.atomic():
                for deposit in queryset.select_for_update().filter(status=Deposit.STATUS_PENDING):
                    wallet = getattr(deposit.user, "wallet", None)
                    if wallet is None:
                        # Should be unreachable now that every User gets a
                        # Wallet via a post_save signal (users/signals.py),
                        # but kept as a safety net for any account that
                        # existed before that signal was added.
                        skipped_no_wallet += 1
                        continue

                    wallet.deposit_balance = wallet.deposit_balance + deposit.amount
                    wallet.save(update_fields=["deposit_balance", "updated_at"])

                    deposit.status = Deposit.STATUS_APPROVED
                    deposit.reviewed_at = timezone.now()
                    deposit.save(update_fields=["status", "reviewed_at"])
                    notify_deposit_decision(deposit, approved=True, remark=remark)
                    approved += 1

            msg = f"Approved {approved} deposit(s) and credited deposit_balance."
            if skipped_no_wallet:
                msg += f" Skipped {skipped_no_wallet} deposit(s) — user has no wallet."
            self.message_user(request, msg)

        return _remark_action(
            self, request, queryset, do_action=do_approve,
            template_name="admin/cashier/remark_intermediate.html",
            description="approve",
        )

    @admin.action(description="Reject selected deposits")
    def reject_deposits(self, request, queryset):
        def do_reject(request, queryset, remark):
            from notifications.services import notify_deposit_decision
            pending = list(queryset.filter(status=Deposit.STATUS_PENDING))
            for deposit in pending:
                deposit.status = Deposit.STATUS_REJECTED
                deposit.reviewed_at = timezone.now()
                deposit.save(update_fields=["status", "reviewed_at"])
                notify_deposit_decision(deposit, approved=False, remark=remark)
            self.message_user(request, f"Rejected {len(pending)} deposit(s).")

        return _remark_action(
            self, request, queryset, do_action=do_reject,
            template_name="admin/cashier/remark_intermediate.html",
            description="reject",
        )


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    search_fields = ["user__email", "status"]
    list_display = ["user", "amount", "currency", "source_wallet", "status", "created_at", "reviewed_at"]
    list_filter = ["status", "currency", "source_wallet"]
    actions = ["approve_withdrawals", "reject_withdrawals"]

    @admin.action(description="Approve selected withdrawals (debits source wallet)")
    def approve_withdrawals(self, request, queryset):
        def do_approve(request, queryset, remark):
            from notifications.services import notify_withdrawal_decision
            approved, skipped, skipped_no_wallet = 0, 0, 0
            with transaction.atomic():
                for withdrawal in queryset.select_for_update().filter(status=Withdrawal.STATUS_PENDING):
                    wallet = getattr(withdrawal.user, "wallet", None)
                    if wallet is None:
                        skipped_no_wallet += 1
                        continue

                    current_balance = getattr(wallet, withdrawal.source_wallet)

                    if current_balance < withdrawal.amount:
                        skipped += 1
                        continue

                    setattr(wallet, withdrawal.source_wallet, current_balance - withdrawal.amount)
                    wallet.save(update_fields=[withdrawal.source_wallet, "updated_at"])

                    withdrawal.status = Withdrawal.STATUS_APPROVED
                    withdrawal.reviewed_at = timezone.now()
                    withdrawal.save(update_fields=["status", "reviewed_at"])
                    notify_withdrawal_decision(withdrawal, approved=True, remark=remark)
                    approved += 1

            msg = f"Approved {approved} withdrawal(s)."
            if skipped:
                msg += f" Skipped {skipped} due to insufficient balance at approval time."
            if skipped_no_wallet:
                msg += f" Skipped {skipped_no_wallet} — user has no wallet."
            self.message_user(request, msg)

        return _remark_action(
            self, request, queryset, do_action=do_approve,
            template_name="admin/cashier/remark_intermediate.html",
            description="approve",
        )

    @admin.action(description="Reject selected withdrawals")
    def reject_withdrawals(self, request, queryset):
        def do_reject(request, queryset, remark):
            from notifications.services import notify_withdrawal_decision
            pending = list(queryset.filter(status=Withdrawal.STATUS_PENDING))
            for withdrawal in pending:
                withdrawal.status = Withdrawal.STATUS_REJECTED
                withdrawal.reviewed_at = timezone.now()
                withdrawal.save(update_fields=["status", "reviewed_at"])
                notify_withdrawal_decision(withdrawal, approved=False, remark=remark)
            self.message_user(request, f"Rejected {len(pending)} withdrawal(s).")

        return _remark_action(
            self, request, queryset, do_action=do_reject,
            template_name="admin/cashier/remark_intermediate.html",
            description="reject",
        )