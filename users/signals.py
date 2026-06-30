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
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User, Wallet


@receiver(post_save, sender=User)
def ensure_wallet_exists(sender, instance, created, **kwargs):
    if created:
        Wallet.objects.get_or_create(user=instance)