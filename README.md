
<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/D%26D-5e%20SRD-cc0000?style=for-the-badge" />
  <img src="https://img.shields.io/badge/LLM-Ollama-7C3AED?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Tests-724%20passing-brightgreen?style=for-the-badge" />
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" />
</p>

<p align="center">
<pre align="center">
         .        .            *       .        .    .      .
    .       *            .        .       .     *         .
        .       .    .        .        .            .
  .        *        .    .        .        .    .        *
              .                  /\
   .     *        .    .        /  \       .        .        .
     .        .        .       / .. \          *        .
  .        .     *     .      /  /\  \    .        .        *
        .        .    .      /  /  \  \       .        .
   *       .        .       /  / /\ \  \  .        *       .
     .        .   *   .    /  / /  \ \  \      .        .
  .     *  .        .     /  / /    \ \  \  .       .      *
    .        .        .  /  / /  ()  \ \  \    .        .
        .        .      /  / / /||\ \ \  \       *
   .        *      .   /  / / / || \ \ \  \  .        .
     .    .     .     /  / / /  ||  \ \ \  \ .    *
  .           *      /  / / /   ||   \ \ \  \        .
    .     .     .   /__/_/_/____||____\_\_\__\   .       .
        .       .   |  _  _  _ _||_ _  _  _  |      .
   *        .       | |_||_||_| || |_||_||_| |  .        *
     .        .     |  _  _  _ _||_ _  _  _  |       .
  .    .   *     .  | |_||_||_| || |_||_||_| |  .
    .        .      |  _  _  _ _||_ _  _  _  |     *    .
        .       .   | |_||_||_| || |_||_||_| |  .        .
   .  *     .       |___________||___________|       .
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ .
    ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~
</pre>
</p>

<h1 align="center">Candlelight Quest</h1>

<p align="center">
  <em>A D&D 5e text RPG where dice are law and the narrator is alive.</em>
</p>

<p align="center">
  Every choice ripples. Every roll matters. The LLM narrates your story,<br/>
  but the d20 decides your fate.
</p>

---

## The Idea

Most text adventures are trees of pre-written branches. Candlelight Quest is different. It uses a local LLM (via Ollama) as a **narrator** — not a game master — while keeping all mechanics grounded in D&D 5e rules with real dice rolls. The LLM doesn't decide if your fireball hits; it describes the way the flames curl around the goblin's shield right before the d20 says it misses.

The result is a game that feels authored and alive, but is mechanically fair.

```
 Morning, Day 3 (08:15)  |  HP [████████░░] 16/20  |  Gold: 47  |  Thornfield Village

 The morning mist curls between the market stalls as merchants begin
 laying out their wares. A blacksmith's hammer rings out from the
 forge at the north end of the square. Old Marta eyes you from behind
 her herbalist's counter, her gaze lingering on the wound across your arm.

 > talk to marta
```

---

## Features

### Core Engine
- **7-step turn loop**: Normalize → Retrieve → Constrain → Propose → Validate → Director → Render
- **Three-ledger SQLite storage**: World State (mutable), Event Ledger (append-only), Canon Ledger (hash-chained)
- **RAG memory**: ChromaDB + nomic-embed-text embeddings — the narrator remembers what happened 50 turns ago
- **TOML-driven content**: Races, classes, items, spells, regions, factions, quests — all data, no code
- **Pure mechanics**: Every calculation in `mechanics/` is a pure function with zero I/O

### Combat
- **D&D 5e initiative** with full turn-based combat
- **Numbered menu**: `[1] Attack  [2] Cast Spell  [3] Use Item  [4] Flee  [5] Dodge`
- **NPC AI**: Enemies flee at <25% HP, target the weakest party member, use abilities tactically
- **Narrative combat**: Each exchange gets 1-2 sentences of LLM-generated prose
- **Wounds system**: Heavy hits (>50% HP damage) cause persistent wounds that need healing
- **Death isn't the end**: Lose 25% gold, respawn weakened at the nearest safe location

### World
- **Director system**: Dynamically spawns NPCs, locations, and quests based on pacing and context
- **Plausibility engine**: Try anything — the LLM evaluates plausibility, sets a DC, dice decide
- **Day/night cycle**: 7 time periods affect NPC schedules, encounters, and survival
- **Survival needs**: Hunger, thirst, warmth, fatigue — affected by climate and rest
- **Faction reputation**: 7 tiers from Hated to Honored — affects prices, quests, guard hostility
- **Bounty system**: Crimes accumulate bounties; bounty hunters spawn on roads above 50

### Character
- **5 races**: Human, Dwarf, Elf, Halfling, Half-Orc — each with racial bonuses
- **4 classes**: Fighter, Wizard, Cleric, Rogue — each with unique features and spell access
- **Multiclassing**: Up to 2 classes with ability prerequisites
- **Spellcasting**: Full slot system with cantrip scaling, concentration, and arcane recovery
- **14 status conditions**: From Blinded to Unconscious, each with mechanical effects

### Systems

| System | What It Does |
|--------|-------------|
| **Combat** | Turn-based D&D 5e with initiative, attacks, spells, and fleeing |
| **Exploration** | Movement, location discovery, environmental puzzles |
| **Social** | NPC dialogue with mood, affinity tracking, conversation mode |
| **Inventory** | Equipment, categories, sorting, encumbrance |
| **Crafting** | 17 recipes across enchanting, alchemy, smithing, cooking |
| **Shop** | Buy/sell with reputation-adjusted prices and restocking |
| **Companion** | Recruit NPCs (affinity ≥15), gift system, combat allies |
| **Housing** | Buy a home, store items, upgrade with bed/garden/crafting station |
| **Spellcasting** | Spell selection, slot management, upcasting |
| **Rest** | Short/long rest, HP recovery, need restoration, wound healing |
| **Director** | Post-turn AI that spawns content and manages narrative pacing |
| **World Sim** | Weather, NPC schedules, faction events |

### Time Travel
- **Snapshot system**: Auto-saves after long rests, region changes, and every 20 turns
- **Rewind command**: Restore world state while keeping player knowledge
- **Timeline tracking**: Hash-chained canon ledger records divergence points
- **RAG persistence**: ChromaDB memories survive across rewinds — déjà vu is a feature

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                             │
│  status_bar · combat_display · map_display · input_handler   │
├─────────────────────────────────────────────────────────────┤
│                      Engine Layer                            │
│   turn_loop · action_dispatcher · validators · snapshots     │
├──────────────┬──────────────────────────────┬───────────────┤
│  Game Systems │      Director System         │   LLM Layer   │
│  combat      │  triggers · generators       │  provider     │
│  exploration │  schemas · cooldowns         │  context_pack │
│  social      │                              │  output_parse │
│  inventory   │                              │  token_budget │
│  crafting    ├──────────────────────────────┤  11 templates │
│  shop        │      Mechanics Layer          │               │
│  companion   │  dice · combat_math          │               │
│  housing     │  conditions · leveling       │               │
│  rest        │  spellcasting · reputation   │               │
│  spellcast   │  survival · wounds · death   │               │
│  world_sim   │  economy · crafting · affinity│               │
├──────────────┴──────────────────────────────┴───────────────┤
│                      Storage Layer                           │
│   database · 14 migrations · 19 repositories                 │
│   Three Ledgers: World State │ Event Ledger │ Canon Ledger   │
├─────────────────────────────────────────────────────────────┤
│                       RAG Layer                              │
│   ChromaDB vector_store · embeddings · retriever · indexer   │
├─────────────────────────────────────────────────────────────┤
│                     Content (TOML)                            │
│   33 files: races · classes · items · spells · regions ·     │
│   factions · encounters · quests · shops · stories           │
└─────────────────────────────────────────────────────────────┘
```

### The Turn Loop

Every player action flows through 7 steps:

```
Player Input
    │
    ▼
┌─────────┐   Regex patterns (41) match first.
│ NORMALIZE│   LLM fallback for ambiguous input.
└────┬────┘
     ▼
┌─────────┐   ChromaDB retrieves relevant lore,
│ RETRIEVE │   past events, and NPC memories.
└────┬────┘
     ▼
┌──────────┐   Rules engine checks: can you cast
│ CONSTRAIN│   that spell? Are you incapacitated?
└────┬─────┘
     ▼
┌─────────┐   Game system resolves the action.
│ PROPOSE │   Dice roll. Mechanics are authoritative.
└────┬────┘
     ▼
┌─────────┐   Mutations validated: HP clamped,
│ VALIDATE│   conditions checked, inventory updated.
└────┬────┘
     ▼
┌─────────┐   Director evaluates pacing. Spawns
│ DIRECTOR│   NPCs, locations, quests as needed.
└────┬────┘
     ▼
┌─────────┐   LLM narrates the result. RAG context
│ RENDER  │   feeds the prose. Rich renders to terminal.
└────┬────┘
     ▼
  Display
```

### Input Classification Pipeline

The input handler is the nervous system of the narrator. It decides **what** the player meant:

```
"cast fireball on the goblin"
         │
         ▼
   ┌───────────┐    41 regex patterns checked in order.
   │ Regex Pass │──→ Match found: action=cast_spell, target=fireball,
   └───────────┘                  spell_target=goblin
         │
         │ No match?
         ▼
   ┌───────────┐    LLM classifies with confidence score.
   │ LLM Pass  │──→ action_classify.j2 → OutputParser
   └───────────┘    Threshold: confidence ≥ 0.4
         │
         │ Below threshold?
         ▼
   ┌─────────────┐  Plausibility engine evaluates.
   │ Plausibility │─→ LLM rates 0-100 → logarithmic DC → skill check
   └─────────────┘
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.ai) running locally with `mistral` and `nomic-embed-text` models

```bash
# Pull the required models
ollama pull mistral
ollama pull nomic-embed-text
```

### Install

```bash
# Clone the repository
git clone https://github.com/Taffesbroodje/candlelight-quest.git
cd candlelight-quest

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e ".[dev]"
```

### Play

```bash
# Check that Ollama is running and models are available
text-rpg check

# Start a new adventure
text-rpg play --new

# Continue a saved game
text-rpg play --save

# List saved games
text-rpg saves
```

### Configuration

Edit `config.toml` to customize:

```toml
[llm]
provider = "ollama"
model = "mistral"           # Any Ollama model
temperature = 0.8           # Narrator creativity

[game]
difficulty = "normal"       # easy, normal, hard
starting_region = "verdant_reach"
starting_location = "thornfield_village"

[display]
narrative_width = 80
show_dice_rolls = true      # See the d20 in action
show_mechanics = true       # Show DC checks and modifiers
```

---

## Commands

### Exploration
| Command | Action |
|---------|--------|
| `go north` / `n` | Move in a direction |
| `look` / `examine chest` | Observe surroundings or objects |
| `search` / `investigate` | Search the area |
| `talk to merchant` | Start a conversation |
| `rest` / `rest long` | Short or long rest |

### Combat
| Command | Action |
|---------|--------|
| `attack goblin` / `1` | Attack a target |
| `2` | Cast a combat spell |
| `3` | Use a combat item |
| `4` / `flee` | Attempt to flee |
| `5` / `dodge` | Take the Dodge action |

### Inventory & Equipment
| Command | Action |
|---------|--------|
| `inventory` / `i` | View inventory |
| `inventory weapons sort value desc` | Filter and sort |
| `equip longsword` | Equip an item |
| `use healing potion` | Use a consumable |
| `craft healing potion` | Craft an item |

### Social
| Command | Action |
|---------|--------|
| `talk to [npc]` | Start dialogue |
| `give potion to healer` | Gift an item to an NPC |
| `recruit wolf` | Recruit a companion (affinity ≥15) |
| `buy longsword` / `sell dagger` | Trade with shops |
| `browse` | View shop inventory |

### Meta
| Command | Action |
|---------|--------|
| `character` / `stats` | View character sheet |
| `spells` / `spellbook` | View known spells |
| `map` | ASCII world map |
| `quests` / `journal` | Quest log |
| `reputation` / `bounty` | Faction standing |
| `rewind` / `undo` | Time travel to last snapshot |
| `home` / `house` | Housing management |
| `save` | Save game |
| `quit` / `q` | Exit |

---

## Testing

The test suite covers 724 parametrized tests across the entire codebase:

```bash
# Run all tests
pytest tests/ -v

# Run specific module tests
pytest tests/test_mechanics/ -v        # Pure game math
pytest tests/test_cli/ -v              # Input classification
pytest tests/test_llm/ -v             # LLM output parsing
pytest tests/test_storage/ -v         # Database & repos
pytest tests/test_engine/ -v          # Validators & turn loop
```

### Test Coverage

| Module | Tests | What's Covered |
|--------|------:|---------------|
| `mechanics/` | ~280 | All 15 mechanics modules: dice, combat, conditions, leveling, reputation, affinity, economy, crafting, death, wounds, spellcasting, multiclassing, survival, world clock, ability scores |
| `cli/` | ~120 | All 41 regex patterns, meta commands, movement, combat choices, conversation handling |
| `llm/` | ~51 | Output parsing (action classification, narrative hooks, dialogue mood, JSON extraction), context packing, token budgeting |
| `engine/` | ~18 | Validators (HP clamping, action validation), turn loop static methods |
| `storage/` | ~14 | Database migrations, schema integrity, commit/rollback, snapshot CRUD |
| `utils/` | ~15 | `safe_json()` and `safe_props()` edge cases |

All tests run in **<1 second** with zero external dependencies — no LLM, no database server, no network calls.

---

## Content

All game content lives in TOML files — add a new race, item, or quest without touching any code:

```
content/
├── classes/          # Fighter, Wizard, Cleric, Rogue
│   └── fighter.toml  # HP dice, proficiencies, features by level
├── races/            # Human, Dwarf, Elf, Halfling, Half-Orc
│   └── dwarf.toml    # Ability bonuses, speed, traits
├── items/            # 6 files: weapons, armor, general, crafting, scrolls, enchanted
├── spells/           # Full spell list with levels, components, effects
├── factions/         # 4 factions with goals, allies, enemies
├── regions/
│   └── verdant_reach/
│       ├── region.toml      # Climate, level range, description
│       ├── locations.toml   # Villages, dungeons, wilderness
│       ├── npcs.toml        # Characters with personalities and schedules
│       ├── encounters.toml  # Combat and puzzle encounters
│       ├── quests.toml      # Quest chains and objectives
│       └── shops.toml       # Merchants and their inventories
└── stories/          # 8 narrative seed files for the Director system
```

### Adding a New Region

Create a new folder under `content/regions/` with the same TOML structure as `verdant_reach/`. The content loader will pick it up automatically.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| LLM | Ollama via LiteLLM |
| Embeddings | nomic-embed-text |
| Vector Store | ChromaDB |
| Database | SQLite (14 migrations) |
| Models | Pydantic v2 |
| Templates | Jinja2 |
| CLI | Typer + Rich |
| Tests | pytest (724 tests) |

---

## Project Structure

```
candlelight-quest/
├── config.toml                    # Game configuration
├── pyproject.toml                 # Python package definition
├── src/text_rpg/
│   ├── app.py                     # Main GameApp bootstrap
│   ├── utils.py                   # safe_json, safe_props
│   ├── cli/                       # Terminal UI (Rich + Typer)
│   ├── content/                   # 33 TOML data files
│   ├── engine/                    # Turn loop, dispatcher, validators
│   ├── llm/                       # LLM provider, parser, 11 templates
│   ├── mechanics/                 # 27 pure-function game math modules
│   ├── models/                    # Pydantic data models
│   ├── rag/                       # ChromaDB + embeddings + retrieval
│   ├── storage/                   # SQLite DB, 14 migrations, 19 repos
│   └── systems/                   # 12 pluggable game systems
└── tests/                         # 724 parametrized tests
    ├── conftest.py                # Shared fixtures
    ├── test_mechanics/            # 15 test modules
    ├── test_cli/                  # Input handler tests
    ├── test_llm/                  # Parser + packer + budget tests
    ├── test_engine/               # Validator + turn loop tests
    └── test_storage/              # DB + snapshot tests
```

---

## Design Philosophy

**Dice are law.** The LLM writes prose, not outcomes. A natural 20 is a critical hit whether the narrator likes it or not.

**Content is data.** Adding a new sword means adding 5 lines of TOML, not writing a Python class.

**Pure mechanics.** Every function in `mechanics/` takes data in and returns data out. No database calls, no network requests, no side effects. This is why 280 mechanics tests run in under a second.

**The Director, not the Dungeon Master.** The Director system watches pacing and spawns content when the world needs it — a new NPC when things are quiet, a bounty hunter when tension is high. It doesn't railroad; it populates.

**Memory makes the narrator.** RAG retrieval means the LLM knows that you killed a merchant 30 turns ago, even when the context window has long forgotten. The narrator references your past because it actually remembers it.

---

<p align="center">
<pre align="center">
        )  (
       (   ) )
        ) ( (
       _____)_
    .-'---------|
   ( C|         |
    '-.         |
      '_________|
       /       \
      /   (.)   \
     |           |
      \  .---.  /
       '-------'

   Light the candle.
   Roll the dice.
   Begin your quest.
</pre>
</p>

<p align="center">
  <sub>Built with obsessive attention to game feel by a human and an AI, one dice roll at a time.</sub>
</p>
