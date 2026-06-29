"""
Helper functions for creating notifications, kept in one place so the
several different call sites (registration, cashier admin actions,
the Django admin promotional/system form) all produce consistently
shaped notifications.
"""
from .models import Notification


def notify_kyc_pending(user):
    """Called once at registration. The KYC notification re-surfaces every
    login via KYCStatusView -- this just creates the initial record."""
    return Notification.objects.create(
        user=user,
        category=Notification.CATEGORY_KYC,
        title="Verify your account",
        message="Complete KYC verification to start trading and withdrawing funds.",
        action_url="/kyc",
        action_label="Verify",
    )


def notify_deposit_decision(deposit, approved: bool, remark: str = ""):
    if approved:
        title = "Deposit approved"
        message = f"Your deposit of {deposit.amount} {deposit.currency} has been approved and credited."
    else:
        title = "Deposit rejected"
        message = f"Your deposit of {deposit.amount} {deposit.currency} was rejected."
    if remark:
        message += f" Remark: {remark}"

    return Notification.objects.create(
        user=deposit.user,
        category=Notification.CATEGORY_DEPOSIT,
        title=title,
        message=message,
        action_url="/cashier?tab=deposit",
        action_label="View",
    )


def notify_withdrawal_decision(withdrawal, approved: bool, remark: str = ""):
    if approved:
        title = "Withdrawal approved"
        message = f"Your withdrawal of {withdrawal.amount} {withdrawal.currency} has been approved."
    else:
        title = "Withdrawal rejected"
        message = f"Your withdrawal of {withdrawal.amount} {withdrawal.currency} was rejected."
    if remark:
        message += f" Remark: {remark}"

    return Notification.objects.create(
        user=withdrawal.user,
        category=Notification.CATEGORY_WITHDRAWAL,
        title=title,
        message=message,
        action_url="/cashier?tab=withdrawal",
        action_label="View",
    )


def notify_broadcast(category, title, message, users=None, action_url="", action_label=""):
    """
    Creates the same notification for multiple users at once (used by
    the admin promotional/system notification form). `users=None`
    means broadcast to every user on the platform.
    """
    from users.models import User

    target_users = users if users is not None else User.objects.all()
    notifications = [
        Notification(
            user=u,
            category=category,
            title=title,
            message=message,
            action_url=action_url,
            action_label=action_label,
        )
        for u in target_users
    ]
    return Notification.objects.bulk_create(notifications)