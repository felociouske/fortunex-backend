"""
Backfills a Wallet for every existing User who doesn't already have
one. Before this fix, Wallet creation was only ever triggered
explicitly inside RegisterSerializer -- any account created another
way (Django admin's "Add user" form, `createsuperuser`, a fixture,
etc.) silently had no wallet, which crashed the moment anything tried
to read `user.wallet` (e.g. approving one of their deposits in admin).

Safe to run multiple times -- uses get_or_create, so it's a no-op for
users that already have a wallet.
"""
from django.db import migrations


def backfill_wallets(apps, schema_editor):
    User = apps.get_model("users", "User")
    Wallet = apps.get_model("users", "Wallet")

    for user in User.objects.all():
        Wallet.objects.get_or_create(user=user)


def noop_reverse(apps, schema_editor):
    # Intentionally not deleting wallets on reverse migration -- that
    # would be destructive and there's no good reason to undo this.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(backfill_wallets, noop_reverse),
    ]