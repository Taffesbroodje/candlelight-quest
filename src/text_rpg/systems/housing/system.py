"""Housing system — buy homes, store items, upgrade."""
from __future__ import annotations

import json
import logging
from typing import Any

from text_rpg.content.loader import load_all_items
from text_rpg.models.action import Action, ActionResult, StateMutation
from text_rpg.systems.base import GameContext, GameSystem
from text_rpg.utils import safe_json

logger = logging.getLogger(__name__)

# Home upgrade definitions
UPGRADES: dict[str, dict[str, Any]] = {
    "bed": {
        "name": "Comfortable Bed",
        "description": "Better rest — long rests restore all hit dice.",
        "cost": 100,
    },
    "garden": {
        "name": "Herb Garden",
        "description": "Produces 1 healing_herb per long rest at home.",
        "cost": 150,
    },
    "crafting_station": {
        "name": "Crafting Station",
        "description": "Reduces crafting DCs by 2 when crafting at home.",
        "cost": 200,
    },
    "display_case": {
        "name": "Trophy Display Case",
        "description": "Store and show off your trophies.",
        "cost": 75,
    },
}

# Default home purchase price
HOME_COST = 500


class HousingSystem(GameSystem):
    def __init__(self, repos: dict[str, Any] | None = None):
        self._repos = repos or {}

    def inject(self, *, repos: dict | None = None, **kwargs) -> None:
        if repos is not None:
            self._repos = repos

    @property
    def system_id(self) -> str:
        return "housing"

    @property
    def handled_action_types(self) -> set[str]:
        return {"buy_home", "store", "retrieve", "upgrade_home", "home"}

    def can_handle(self, action: Action, context: GameContext) -> bool:
        return action.action_type.lower() in self.handled_action_types

    def resolve(self, action: Action, context: GameContext) -> ActionResult:
        action_type = action.action_type.lower()
        if action_type == "buy_home":
            return self._buy_home(action, context)
        elif action_type == "store":
            return self._store_item(action, context)
        elif action_type == "retrieve":
            return self._retrieve_item(action, context)
        elif action_type == "upgrade_home":
            return self._upgrade_home(action, context)
        elif action_type == "home":
            return self._show_home(action, context)
        return ActionResult(action_id=action.id, success=False, outcome_description="Unknown housing action.")

    def get_available_actions(self, context: GameContext) -> list[dict]:
        housing_repo = self._repos.get("housing")
        if not housing_repo:
            return []
        home = housing_repo.get_home(context.game_id, context.character.get("id", ""))
        if home:
            return [
                {"action_type": "store", "description": "Store an item at home"},
                {"action_type": "retrieve", "description": "Retrieve an item from storage"},
                {"action_type": "upgrade_home", "description": "Upgrade your home"},
            ]
        # Check if current location is purchasable
        loc = context.location
        props = safe_json(loc.get("properties"), {})
        if props.get("purchasable"):
            return [{"action_type": "buy_home", "description": f"Buy this property ({props.get('price', HOME_COST)} gold)"}]
        return []

    def _buy_home(self, action: Action, context: GameContext) -> ActionResult:
        """Purchase the current location as a home."""
        housing_repo = self._repos.get("housing")
        if not housing_repo:
            return ActionResult(action_id=action.id, success=False, outcome_description="Housing system unavailable.")

        char_id = context.character.get("id", "")
        existing = housing_repo.get_home(context.game_id, char_id)
        if existing:
            return ActionResult(action_id=action.id, success=False, outcome_description="You already own a home.")

        loc = context.location
        props = safe_json(loc.get("properties"), {})

        if not props.get("purchasable"):
            return ActionResult(action_id=action.id, success=False, outcome_description="This location is not for sale.")

        price = props.get("price", HOME_COST)
        gold = context.character.get("gold", 0)
        if gold < price:
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description=f"You need {price} gold to buy this home (you have {gold}).",
            )

        home_name = props.get("home_name", f"{loc.get('name', 'Home')}")
        housing_repo.buy_home(context.game_id, char_id, loc["id"], home_name, context.turn_number)

        mutations = [
            StateMutation(
                target_type="character", target_id=char_id,
                field="gold", old_value=gold, new_value=gold - price,
            ),
        ]

        return ActionResult(
            action_id=action.id, success=True,
            outcome_description=f"You purchase {home_name} for {price} gold! This is now your home.",
            state_mutations=mutations,
            events=[{"event_type": "HOME_PURCHASED", "description": f"Purchased {home_name} for {price} gold."}],
        )

    def _store_item(self, action: Action, context: GameContext) -> ActionResult:
        """Store an item from inventory into home storage."""
        housing_repo = self._repos.get("housing")
        if not housing_repo:
            return ActionResult(action_id=action.id, success=False, outcome_description="Housing system unavailable.")

        char_id = context.character.get("id", "")
        home = housing_repo.get_home(context.game_id, char_id)
        if not home:
            return ActionResult(action_id=action.id, success=False, outcome_description="You don't own a home.")

        # Check if at home location
        if context.location.get("id") != home.get("location_id"):
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description="You need to be at your home to store items.",
            )

        item_name = (action.target_id or "").lower()
        if not item_name:
            return ActionResult(action_id=action.id, success=False, outcome_description="Store what? Specify an item.")

        # Find item in inventory
        inv = context.inventory or []
        if isinstance(inv, dict):
            inv = inv.get("items", [])
        all_items = load_all_items()
        found = None
        for entry in inv:
            iid = entry.get("item_id", "")
            item_data = all_items.get(iid, {})
            if item_name in iid.lower() or item_name in item_data.get("name", "").lower():
                found = (iid, item_data)
                break

        if not found:
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description=f"You don't have '{item_name}' in your inventory.",
            )

        item_id, item_data = found
        housing_repo.store_item(context.game_id, char_id, item_id)

        mutations = [
            StateMutation(
                target_type="inventory", target_id=char_id,
                field="items_remove_one", old_value=None,
                new_value=json.dumps({"item_id": item_id}),
            ),
        ]

        display_name = item_data.get("name", item_id.replace("_", " ").title())
        return ActionResult(
            action_id=action.id, success=True,
            outcome_description=f"You store {display_name} in your home.",
            state_mutations=mutations,
            events=[{"event_type": "ITEM_STORED", "description": f"Stored {display_name} at home."}],
        )

    def _retrieve_item(self, action: Action, context: GameContext) -> ActionResult:
        """Retrieve an item from home storage into inventory."""
        housing_repo = self._repos.get("housing")
        if not housing_repo:
            return ActionResult(action_id=action.id, success=False, outcome_description="Housing system unavailable.")

        char_id = context.character.get("id", "")
        home = housing_repo.get_home(context.game_id, char_id)
        if not home:
            return ActionResult(action_id=action.id, success=False, outcome_description="You don't own a home.")

        if context.location.get("id") != home.get("location_id"):
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description="You need to be at your home to retrieve items.",
            )

        item_name = (action.target_id or "").lower()
        if not item_name:
            return ActionResult(action_id=action.id, success=False, outcome_description="Retrieve what? Specify an item.")

        storage = housing_repo.get_storage_items(context.game_id, char_id)
        all_items = load_all_items()
        found_id = None
        for entry in storage:
            iid = entry.get("item_id", "")
            item_data = all_items.get(iid, {})
            if item_name in iid.lower() or item_name in item_data.get("name", "").lower():
                found_id = iid
                break

        if not found_id:
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description=f"No '{item_name}' found in your home storage.",
            )

        if not housing_repo.retrieve_item(context.game_id, char_id, found_id):
            return ActionResult(action_id=action.id, success=False, outcome_description="Failed to retrieve item.")

        mutations = [
            StateMutation(
                target_type="inventory", target_id=char_id,
                field="items_add", old_value=None,
                new_value=json.dumps({"item_id": found_id, "quantity": 1}),
            ),
        ]

        display_name = all_items.get(found_id, {}).get("name", found_id.replace("_", " ").title())
        return ActionResult(
            action_id=action.id, success=True,
            outcome_description=f"You retrieve {display_name} from storage.",
            state_mutations=mutations,
            events=[{"event_type": "ITEM_RETRIEVED", "description": f"Retrieved {display_name} from home."}],
        )

    def _upgrade_home(self, action: Action, context: GameContext) -> ActionResult:
        """Upgrade your home with a new feature."""
        housing_repo = self._repos.get("housing")
        if not housing_repo:
            return ActionResult(action_id=action.id, success=False, outcome_description="Housing system unavailable.")

        char_id = context.character.get("id", "")
        home = housing_repo.get_home(context.game_id, char_id)
        if not home:
            return ActionResult(action_id=action.id, success=False, outcome_description="You don't own a home.")

        if context.location.get("id") != home.get("location_id"):
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description="You need to be at your home to upgrade it.",
            )

        upgrade_name = (action.target_id or "").lower().replace(" ", "_")
        if not upgrade_name:
            # List available upgrades
            current = housing_repo.get_upgrades(context.game_id, char_id)
            lines = ["Available upgrades:"]
            for uid, udef in UPGRADES.items():
                status = " (owned)" if uid in current else f" ({udef['cost']} gold)"
                lines.append(f"  {udef['name']}{status} — {udef['description']}")
            return ActionResult(action_id=action.id, success=True, outcome_description="\n".join(lines))

        if upgrade_name not in UPGRADES:
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description=f"Unknown upgrade '{upgrade_name}'. Valid: {', '.join(UPGRADES.keys())}",
            )

        current_upgrades = housing_repo.get_upgrades(context.game_id, char_id)
        if upgrade_name in current_upgrades:
            return ActionResult(action_id=action.id, success=False, outcome_description="You already have that upgrade.")

        upgrade_def = UPGRADES[upgrade_name]
        gold = context.character.get("gold", 0)
        cost = upgrade_def["cost"]
        if gold < cost:
            return ActionResult(
                action_id=action.id, success=False,
                outcome_description=f"You need {cost} gold for {upgrade_def['name']} (you have {gold}).",
            )

        housing_repo.add_upgrade(context.game_id, char_id, upgrade_name)

        mutations = [
            StateMutation(
                target_type="character", target_id=char_id,
                field="gold", old_value=gold, new_value=gold - cost,
            ),
        ]

        return ActionResult(
            action_id=action.id, success=True,
            outcome_description=f"You install {upgrade_def['name']} for {cost} gold! {upgrade_def['description']}",
            state_mutations=mutations,
            events=[{"event_type": "HOME_UPGRADED", "description": f"Installed {upgrade_def['name']}."}],
        )

    def _show_home(self, action: Action, context: GameContext) -> ActionResult:
        """Show home status."""
        housing_repo = self._repos.get("housing")
        if not housing_repo:
            return ActionResult(action_id=action.id, success=False, outcome_description="Housing system unavailable.")

        char_id = context.character.get("id", "")
        home = housing_repo.get_home(context.game_id, char_id)
        if not home:
            return ActionResult(action_id=action.id, success=True, outcome_description="You don't own a home yet.")

        all_items = load_all_items()
        storage = housing_repo.get_storage_items(context.game_id, char_id)
        upgrades = housing_repo.get_upgrades(context.game_id, char_id)

        lines = [f"Your home: {home.get('name', 'Home')}"]
        if upgrades:
            upgrade_names = [UPGRADES.get(u, {}).get("name", u) for u in upgrades]
            lines.append(f"Upgrades: {', '.join(upgrade_names)}")
        if storage:
            storage_names = []
            for entry in storage:
                iid = entry.get("item_id", "")
                qty = entry.get("quantity", 1)
                name = all_items.get(iid, {}).get("name", iid.replace("_", " ").title())
                storage_names.append(f"{name} x{qty}" if qty > 1 else name)
            lines.append(f"Storage: {', '.join(storage_names)}")
        else:
            lines.append("Storage: empty")

        return ActionResult(action_id=action.id, success=True, outcome_description="\n".join(lines))
