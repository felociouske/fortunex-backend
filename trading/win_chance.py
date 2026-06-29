"""
Resolves a user's currently active win-chance and which contract types
they have unlocked, based on their active bot/AI automation (if any).

This is intentionally the ONLY place that reads "what tier is this user
on" -- both contract opening (to record win_chance_source for audit) and
settlement (to know the coin-flip weighting) call into this, so the two
can never disagree about which tier is active.
"""
from dataclasses import dataclass

from trading.contract_types import BASELINE_WIN_CHANCE, unlocked_contracts_for_count


@dataclass
class ActiveTier:
    win_chance: float
    unlocked_contracts: list[str]
    source_label: str  # e.g. "Momentum Bot" or "baseline" -- for audit trail


def resolve_active_tier(user) -> ActiveTier:
    """
    Returns the win-chance and unlocked contract list currently in
    effect for `user`. Falls back to the baseline (3%, Rise/Fall only)
    if they have no active bot/AI -- this is the ONLY fallback path;
    a missing/broken automation row should never raise, since trading
    must keep working even if something is misconfigured.
    """
    # Local import avoids a circular import at module load time, since
    # bots.services also imports from trading (contract_types).
    from bots.services import get_active_automation

    automation = get_active_automation(user)
    if automation is None:
        return ActiveTier(
            win_chance=BASELINE_WIN_CHANCE,
            unlocked_contracts=unlocked_contracts_for_count(1),
            source_label="baseline",
        )

    product = automation.product
    return ActiveTier(
        win_chance=float(product.win_chance),
        unlocked_contracts=unlocked_contracts_for_count(product.unlocked_contract_count),
        source_label=product.name,
    )