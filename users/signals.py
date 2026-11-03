"""
Guarantees every User row has a Wallet, no matter how the User was
created -- through registration (RegisterSerializer, which already
creates one explicitly), Django admin's "Add user" form, `manage.py
createsuperuser`, a data migration, a test fixture, or anything else.

Without this, any user created outside the registration flow silently
has no wallet, which then crashes (RelatedObjectDoesNotExist) the
moment anything tries to touch `user.wallet` -- e.g. an admin trying
to approve one of their deposits. A signal at the model level closes
this gap permanently, for every creation path at once, rather than
needing every individual creation path to remember to create a wallet.
"""
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User, Wallet
from .wallet_events import broadcast_wallet_update


@receiver(post_save, sender=User)
def ensure_wallet_exists(sender, instance, created, **kwargs):
    if created:
        Wallet.objects.get_or_create(user=instance)


@receiver(post_save, sender=Wallet)
def push_wallet_update(sender, instance, **kwargs):
    """
    Fires on EVERY Wallet.save(): stake debits, settlement payouts,
    deposits, withdrawals, bot purchases, referral commissions. No call
    site needs to remember to broadcast.

    Wrapped in on_commit so the browser is never told about a balance
    the database hasn't durably saved yet (a rollback would otherwise
    leave the UI showing money that doesn't exist). Outside a
    transaction, on_commit runs immediately.

    Limitation: queryset .update() and F() expressions skip signals. No
    wallet code uses them today; if that ever changes, call
    broadcast_wallet_update(user_id) manually after it.
    """
    user_id = instance.user_id
    transaction.on_commit(
        lambda: broadcast_wallet_update(user_id),
        using=kwargs.get("using"),
    )