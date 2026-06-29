"""
Business logic for purchasing a bot or AI automation tier.

Kept separate from views.py because this single operation touches three
different concerns that each deserve to be readable on their own:
  1. Debiting the buyer's deposit_balance (the ONLY wallet bots/AIs can
     be purchased from, per the platform's wallet rules).
  2. Deactivating whatever automation (bot OR AI) was previously active
     for this user -- only one is ever active at a time, and the most
     recently purchased one always wins.
  3. Paying a referral commission into the REFERRER's yield_balance, if
     the buyer was referred by someone (User.referred_by).
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from affiliate.models import ReferralCommission
from .models import AutomationProduct, UserAutomation


@transaction.atomic
def purchase_automation(user, product: AutomationProduct) -> UserAutomation:
    """
    Purchase and activate `product` for `user`. Raises ValueError if the
    user's deposit_balance is insufficient -- callers should validate
    this earlier (see PurchaseAutomationSerializer) so this is really a
    defence-in-depth check against race conditions, not the primary
    validation path.
    """
    # Lock the wallet row for the duration of this purchase so two
    # concurrent purchase requests can't both pass the balance check
    # against the same starting balance.
    wallet = user.wallet.__class__.objects.select_for_update().get(user=user)

    if wallet.deposit_balance < product.price:
        raise ValueError("Insufficient deposit balance for this purchase.")

    wallet.deposit_balance = wallet.deposit_balance - product.price
    wallet.save(update_fields=["deposit_balance", "updated_at"])

    # Deactivate whatever automation (bot OR AI) was previously active.
    # Only one is ever active at a time, regardless of kind.
    UserAutomation.objects.filter(user=user, active=True).update(
        active=False, deactivated_at=timezone.now()
    )

    automation = UserAutomation.objects.create(user=user, product=product, active=True)

    _pay_referral_commission(user, product)

    return automation


def _pay_referral_commission(buyer, product: AutomationProduct):
    """
    If `buyer` was referred by someone, credit that referrer's
    yield_balance with `product.price * product.commission_rate` and
    log a ReferralCommission row. No-op if the buyer wasn't referred.
    """
    referrer = buyer.referred_by
    if referrer is None:
        return

    commission_amount = (product.price * product.commission_rate).quantize(Decimal("0.01"))
    if commission_amount <= 0:
        return

    referrer_wallet = referrer.wallet.__class__.objects.select_for_update().get(user=referrer)
    referrer_wallet.yield_balance = referrer_wallet.yield_balance + commission_amount
    referrer_wallet.save(update_fields=["yield_balance", "updated_at"])

    ReferralCommission.objects.create(
        referrer=referrer,
        referred=buyer,
        amount=commission_amount,
        description=f"Commission for {buyer.email}'s purchase of {product.name}",
    )


def get_active_automation(user) -> UserAutomation | None:
    """Returns the user's currently active automation row, or None if they have none."""
    return UserAutomation.objects.filter(user=user, active=True).select_related("product").first()