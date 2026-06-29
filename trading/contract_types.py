"""
Canonical contract type definitions and their strict unlock order.

This is the single source of truth both the `bots` app (which decides
how many contract types a given automation tier unlocks) and the
`trading` app (which decides which contracts a user is currently
allowed to trade, and how each one settles) read from. Defining it
once here avoids the two apps silently drifting out of sync.

Unlock order is fixed and additive: tier N always unlocks everything
tier N-1 unlocked, plus one more (per the confirmed product spec) --
never a different combination at the same count.
"""

RISE_FALL = "RISE_FALL"
EVEN_ODD = "EVEN_ODD"
HIGHER_LOWER = "HIGHER_LOWER"
OVER_UNDER = "OVER_UNDER"
MATCHES_DIFFERS = "MATCHES_DIFFERS"
TOUCH_NO_TOUCH = "TOUCH_NO_TOUCH"

# Index 0 = unlocked first (baseline, no automation needed).
# Index 5 = unlocked last (requires the top tier / "all contracts").
CONTRACT_UNLOCK_ORDER = [
    RISE_FALL,
    EVEN_ODD,
    HIGHER_LOWER,
    OVER_UNDER,
    MATCHES_DIFFERS,
    TOUCH_NO_TOUCH,
]

CONTRACT_LABELS = {
    RISE_FALL: "Rise/Fall",
    EVEN_ODD: "Even/Odd",
    HIGHER_LOWER: "Higher/Lower",
    OVER_UNDER: "Over/Under",
    MATCHES_DIFFERS: "Matches/Differs",
    TOUCH_NO_TOUCH: "Touch/No Touch",
}

TOTAL_CONTRACT_COUNT = len(CONTRACT_UNLOCK_ORDER)


def unlocked_contracts_for_count(count: int) -> list[str]:
    """
    Returns the list of contract type codes unlocked for a given
    unlock count (e.g. count=3 -> [RISE_FALL, EVEN_ODD, HIGHER_LOWER]).
    Clamped to the valid range so a bad value (0, negative, or >6
    from a misconfigured product) never crashes -- it just unlocks
    nothing or everything instead.
    """
    clamped = max(0, min(count, TOTAL_CONTRACT_COUNT))
    return CONTRACT_UNLOCK_ORDER[:clamped]


# Baseline: a user with no active bot/AI can only trade Rise/Fall, at
# the 3% baseline win chance. This mirrors AutomationProduct's shape
# without requiring a real database row for "no automation".
BASELINE_WIN_CHANCE = 0.03
BASELINE_UNLOCKED_CONTRACTS = unlocked_contracts_for_count(1)