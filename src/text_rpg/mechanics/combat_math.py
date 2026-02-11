"""Combat math — pure functions, no I/O."""
from __future__ import annotations

import random

from text_rpg.mechanics.dice import DiceResult, roll, roll_d20, roll_with_advantage, roll_with_disadvantage


def attack_roll(
    attack_bonus: int,
    target_ac: int,
    advantage: bool = False,
    disadvantage: bool = False,
) -> tuple[bool, bool, DiceResult]:
    """Make an attack roll. Returns (hit, is_critical, dice_result).

    Natural 20 always hits and is critical. Natural 1 always misses.
    """
    if advantage and not disadvantage:
        result, _, _ = roll_with_advantage()
    elif disadvantage and not advantage:
        result, _, _ = roll_with_disadvantage()
    else:
        result = roll_d20()

    natural_roll = result.individual_rolls[0]
    result.modifier = attack_bonus
    result.total = natural_roll + attack_bonus

    is_critical = natural_roll == 20
    is_nat_one = natural_roll == 1

    if is_nat_one:
        return False, False, result
    if is_critical:
        return True, True, result

    hit = result.total >= target_ac
    return hit, False, result


def damage_roll(damage_dice: str, damage_modifier: int, is_critical: bool = False) -> DiceResult:
    """Roll damage. Critical doubles the dice count."""
    if is_critical:
        # Double the dice: "1d8" -> "2d8", "2d6" -> "4d6"
        parts = damage_dice.lower().split("d")
        if len(parts) == 2:
            num = int(parts[0]) * 2
            damage_dice = f"{num}d{parts[1]}"

    result = roll(damage_dice)
    result.modifier = damage_modifier
    result.total = sum(result.individual_rolls) + damage_modifier
    if result.total < 0:
        result.total = 0
    return result


def calculate_ac(
    armor_ac_base: int,
    dex_modifier: int,
    armor_type: str,
    shield: bool = False,
    other_bonuses: int = 0,
) -> int:
    """Calculate AC based on armor type."""
    if armor_type == "light":
        ac = armor_ac_base + dex_modifier
    elif armor_type == "medium":
        ac = armor_ac_base + min(dex_modifier, 2)
    elif armor_type == "heavy":
        ac = armor_ac_base
    else:
        ac = armor_ac_base + dex_modifier

    if shield:
        ac += 2
    return ac + other_bonuses


def calculate_ac_unarmored(dex_modifier: int, other_bonuses: int = 0) -> int:
    """Calculate unarmored AC: 10 + DEX + bonuses."""
    return 10 + dex_modifier + other_bonuses


def initiative_roll(dex_modifier: int) -> DiceResult:
    """Roll initiative: 1d20 + DEX modifier."""
    result = roll_d20(modifier=dex_modifier)
    return result


def determine_turn_order(combatants: list[tuple[str, int]]) -> list[str]:
    """Sort combatants by initiative (highest first, random tiebreak).

    Args:
        combatants: list of (entity_id, initiative_total)
    Returns:
        list of entity_ids sorted by initiative
    """
    shuffled = [(eid, init, random.random()) for eid, init in combatants]
    shuffled.sort(key=lambda x: (x[1], x[2]), reverse=True)
    return [eid for eid, _, _ in shuffled]


def calculate_flee_dc(enemy_count: int) -> int:
    """Calculate DC to flee from combat: 10 + 2 per enemy."""
    return 10 + 2 * max(enemy_count, 1)


def assess_threat_level(player_level: int, enemy_level: int) -> str:
    """Assess threat of an enemy relative to the player.

    Returns one of: 'trivial', 'easy', 'normal', 'hard', 'deadly', 'overwhelming'.
    """
    diff = enemy_level - player_level
    if diff <= -5:
        return "trivial"
    if diff <= -2:
        return "easy"
    if diff <= 1:
        return "normal"
    if diff <= 3:
        return "hard"
    if diff <= 5:
        return "deadly"
    return "overwhelming"


def npc_choose_action(npc: dict, targets: list[dict], context: dict | None = None) -> dict:
    """Simple NPC combat AI. Returns action dict.

    Logic:
    - HP < 25% of max → attempt to flee
    - Otherwise → attack the closest/weakest target
    """
    hp = npc.get("hp", {})
    if isinstance(hp, dict):
        current = hp.get("current", 10)
        maximum = hp.get("max", 10)
    else:
        current = npc.get("hp_current", 10)
        maximum = npc.get("hp_max", 10)

    # Flee if low HP
    if maximum > 0 and current / maximum < 0.25:
        return {"action": "flee", "npc_id": npc.get("entity_id", npc.get("id", ""))}

    # Pick target — prefer weakest alive target
    alive_targets = [t for t in targets if t.get("hp", {}).get("current", 1) > 0]
    if not alive_targets:
        return {"action": "dodge", "npc_id": npc.get("entity_id", npc.get("id", ""))}

    # Attack the target with lowest HP
    target = min(alive_targets, key=lambda t: t.get("hp", {}).get("current", 999))
    return {
        "action": "attack",
        "npc_id": npc.get("entity_id", npc.get("id", "")),
        "target_id": target.get("entity_id", target.get("id", "")),
    }
