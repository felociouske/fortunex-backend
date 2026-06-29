"""
Shared stake-funding logic used by both manual contract opening
(OpenContractSerializer/OpenContractView) and bot-run automation
(botrun_engine.py) -- kept in one place so the two can never drift
apart on how a stake is funded or debited.

Rule (confirmed product decision): the two wallets are treated as one
combined pool for staking purposes. real_balance is drained first;
whatever's left of the stake is drawn from deposit_balance. If the
combined total can't cover the stake, the whole request is rejected
-- there is no partial trade.
"""
from decimal import Decimal


class InsufficientFunds(Exception):
    pass


def check_stake_affordable(wallet, stake: Decimal):
    """Raises InsufficientFunds if real_balance + deposit_balance can't cover `stake`."""
    available = wallet.real_balance + wallet.deposit_balance
    if stake > available:
        raise InsufficientFunds("Insufficient funds. Please top up your balance.")


def debit_stake(wallet, stake: Decimal):
    """
    Debits `stake` from `wallet`, draining real_balance to 0 first and
    pulling any remainder from deposit_balance. Caller is responsible
    for locking the wallet row (select_for_update) and saving it
    afterwards -- this function only mutates the in-memory object so it
    can be combined with other field updates in a single .save() call.

    Raises InsufficientFunds if the combined total can't cover the
    stake (callers should usually call check_stake_affordable first to
    fail fast with a clean validation error, but this is enforced here
    too as defence-in-depth against race conditions).
    """
    check_stake_affordable(wallet, stake)

    if wallet.real_balance >= stake:
        wallet.real_balance = wallet.real_balance - stake
        return

    remainder = stake - wallet.real_balance
    wallet.real_balance = Decimal("0")
    wallet.deposit_balance = wallet.deposit_balance - remainder