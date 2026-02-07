from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NationBlueprint:
    name: str
    bonus: str
    gather_bonus: float
    research_bonus: float
    training_bonus: float
    defense_bonus: float


NATIONS: tuple[NationBlueprint, ...] = (
    NationBlueprint(
        name="Aurelian Dominion",
        bonus="Faster research speed",
        gather_bonus=1.0,
        research_bonus=1.15,
        training_bonus=1.0,
        defense_bonus=1.05,
    ),
    NationBlueprint(
        name="Verdant Circle",
        bonus="More efficient food production",
        gather_bonus=1.05,
        research_bonus=1.0,
        training_bonus=1.0,
        defense_bonus=1.05,
    ),
    NationBlueprint(
        name="Ironclad Compact",
        bonus="Cheaper fortifications",
        gather_bonus=1.0,
        research_bonus=1.0,
        training_bonus=1.0,
        defense_bonus=1.15,
    ),
    NationBlueprint(
        name="Skyforge Union",
        bonus="Reduced unit training time",
        gather_bonus=1.0,
        research_bonus=1.0,
        training_bonus=1.2,
        defense_bonus=1.0,
    ),
    NationBlueprint(
        name="Crimson Choir",
        bonus="Higher mana generation",
        gather_bonus=1.05,
        research_bonus=1.05,
        training_bonus=1.0,
        defense_bonus=1.0,
    ),
    NationBlueprint(
        name="Ashen Freeholds",
        bonus="Increased worker carry capacity",
        gather_bonus=1.15,
        research_bonus=1.0,
        training_bonus=1.0,
        defense_bonus=1.0,
    ),
    NationBlueprint(
        name="Obsidian Covenant",
        bonus="Cheaper unit upgrades",
        gather_bonus=1.0,
        research_bonus=1.05,
        training_bonus=1.0,
        defense_bonus=1.1,
    ),
    NationBlueprint(
        name="Tideborne Assembly",
        bonus="Reduced naval unit cost",
        gather_bonus=1.0,
        research_bonus=1.0,
        training_bonus=1.05,
        defense_bonus=1.05,
    ),
)

TECH_TIERS = (
    {"name": "Tier 1", "cost": {"gold": 0, "lumber": 0, "arcana": 0}},
    {"name": "Tier 2", "cost": {"gold": 300, "lumber": 200, "arcana": 0}},
    {"name": "Tier 3", "cost": {"gold": 600, "lumber": 400, "arcana": 50}},
    {"name": "Tier 4", "cost": {"gold": 900, "lumber": 600, "arcana": 120}},
)

ZOMBIE_PHASES = (
    {
        "name": "Scouting Swarm",
        "start": 0,
        "threat_multiplier": 0.8,
        "special": "Basic shamblers test defenses.",
    },
    {
        "name": "Corruption Spread",
        "start": 15,
        "threat_multiplier": 1.1,
        "special": "Burrowers, spitters, and corruption zones emerge.",
    },
    {
        "name": "Siege of the Living",
        "start": 30,
        "threat_multiplier": 1.5,
        "special": "Siege zombies target structures and nests expand.",
    },
    {
        "name": "The Dark Tide",
        "start": 45,
        "threat_multiplier": 2.1,
        "special": "Boss-level undead leaders and mega-waves arrive.",
    },
)
