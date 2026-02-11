"""Class-specific resource mechanics — pure functions, no I/O."""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Rage (Barbarian)
# ---------------------------------------------------------------------------

_RAGE_USES = {
    1: 2, 2: 2, 3: 3, 4: 3, 5: 3, 6: 4, 7: 4, 8: 4, 9: 4, 10: 4,
    11: 4, 12: 5, 13: 5, 14: 5, 15: 5, 16: 5, 17: 6, 18: 6, 19: 6, 20: 999,
}

_RAGE_DAMAGE = {
    1: 2, 2: 2, 3: 2, 4: 2, 5: 2, 6: 2, 7: 2, 8: 2,
    9: 3, 10: 3, 11: 3, 12: 3, 13: 3, 14: 3, 15: 3,
    16: 4, 17: 4, 18: 4, 19: 4, 20: 4,
}


def get_rage_uses(barbarian_level: int) -> int:
    """Number of rages per long rest at given barbarian level."""
    clamped = min(max(barbarian_level, 1), 20)
    return _RAGE_USES[clamped]


def calculate_rage_damage(barbarian_level: int) -> int:
    """Bonus melee damage while raging."""
    clamped = min(max(barbarian_level, 1), 20)
    return _RAGE_DAMAGE[clamped]


def rage_resistances() -> list[str]:
    """Damage types resisted while raging."""
    return ["bludgeoning", "piercing", "slashing"]


# ---------------------------------------------------------------------------
# Ki (Monk)
# ---------------------------------------------------------------------------

def get_ki_points(monk_level: int) -> int:
    """Ki points = monk level. Recharge on short or long rest."""
    return max(monk_level, 0)


def ki_ability_dc(wisdom_score: int, prof_bonus: int) -> int:
    """Ki save DC = 8 + WIS modifier + proficiency bonus."""
    wis_mod = (wisdom_score - 10) // 2
    return 8 + wis_mod + prof_bonus


# ---------------------------------------------------------------------------
# Sorcery Points (Sorcerer)
# ---------------------------------------------------------------------------

def get_sorcery_points(sorcerer_level: int) -> int:
    """Sorcery points = sorcerer level (available from level 2)."""
    if sorcerer_level < 2:
        return 0
    return sorcerer_level


_POINTS_TO_SLOT: dict[int, int] = {2: 1, 3: 2, 5: 3, 6: 4, 7: 5}
_SLOT_TO_POINTS: dict[int, int] = {1: 2, 2: 3, 3: 5, 4: 6, 5: 7}


def slot_to_points(slot_level: int) -> int:
    """Convert a spell slot into sorcery points."""
    return _SLOT_TO_POINTS.get(slot_level, slot_level + 1)


def points_to_slot(points: int) -> int | None:
    """Convert sorcery points into a spell slot. Returns slot level or None."""
    return _POINTS_TO_SLOT.get(points)


# ---------------------------------------------------------------------------
# Lay on Hands (Paladin)
# ---------------------------------------------------------------------------

def get_lay_on_hands_pool(paladin_level: int) -> int:
    """Lay on Hands healing pool = paladin level * 5."""
    return max(paladin_level, 0) * 5


# ---------------------------------------------------------------------------
# Bardic Inspiration (Bard)
# ---------------------------------------------------------------------------

def get_inspiration_uses(charisma_score: int) -> int:
    """Bardic Inspiration uses per long rest = max(1, CHA modifier)."""
    cha_mod = (charisma_score - 10) // 2
    return max(1, cha_mod)


def get_inspiration_die(bard_level: int) -> str:
    """Bardic Inspiration die size by bard level."""
    if bard_level >= 15:
        return "1d12"
    if bard_level >= 10:
        return "1d10"
    if bard_level >= 5:
        return "1d8"
    return "1d6"


# ---------------------------------------------------------------------------
# Wild Shape (Druid)
# ---------------------------------------------------------------------------

def get_wild_shape_uses() -> int:
    """Wild Shape uses per short rest (always 2)."""
    return 2


def get_wild_shape_temp_hp(druid_level: int) -> int:
    """Temp HP gained when Wild Shaping = druid level * 4."""
    return max(druid_level, 0) * 4


# ---------------------------------------------------------------------------
# Divine Smite (Paladin)
# ---------------------------------------------------------------------------

def calculate_smite_damage(slot_level: int, is_undead_or_fiend: bool = False) -> str:
    """Calculate Divine Smite damage dice string.

    Base 2d8 + 1d8 per level above 1st + 1d8 vs undead/fiend. Max 5d8 base.
    """
    num_dice = min(1 + slot_level, 5)  # 2d8 at L1, cap at 5d8
    if is_undead_or_fiend:
        num_dice += 1
    return f"{num_dice}d8"


# ---------------------------------------------------------------------------
# Warlock Pact Magic
# ---------------------------------------------------------------------------

_PACT_SLOTS: dict[int, tuple[int, int]] = {
    1: (1, 1), 2: (2, 1), 3: (2, 2), 4: (2, 2),
    5: (2, 3), 6: (2, 3), 7: (2, 4), 8: (2, 4),
    9: (2, 5), 10: (2, 5), 11: (3, 5), 12: (3, 5),
    13: (3, 5), 14: (3, 5), 15: (3, 5), 16: (3, 5),
    17: (4, 5), 18: (4, 5), 19: (4, 5), 20: (4, 5),
}


def get_pact_slots(warlock_level: int) -> tuple[int, int]:
    """Return (num_slots, slot_level) for warlock Pact Magic."""
    clamped = min(max(warlock_level, 1), 20)
    return _PACT_SLOTS[clamped]
