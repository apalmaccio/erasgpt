from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from .data import NATIONS, TECH_TIERS, ZOMBIE_PHASES, NationBlueprint


@dataclass
class Resources:
    gold: int = 500
    lumber: int = 300
    food: int = 10
    arcana: int = 0

    def can_afford(self, cost: dict[str, int]) -> bool:
        return (
            self.gold >= cost.get("gold", 0)
            and self.lumber >= cost.get("lumber", 0)
            and self.arcana >= cost.get("arcana", 0)
        )

    def spend(self, cost: dict[str, int]) -> None:
        self.gold -= cost.get("gold", 0)
        self.lumber -= cost.get("lumber", 0)
        self.arcana -= cost.get("arcana", 0)

    def add(self, gold: int = 0, lumber: int = 0, food: int = 0, arcana: int = 0) -> None:
        self.gold += gold
        self.lumber += lumber
        self.food += food
        self.arcana += arcana


@dataclass
class Nation:
    blueprint: NationBlueprint
    resources: Resources = field(default_factory=Resources)
    workers: int = 8
    soldiers: int = 6
    tech_tier: int = 1
    base_health: int = 100
    morale: float = 1.0
    supply_used: int = 6
    alive: bool = True

    def gather_resources(self) -> None:
        if not self.alive:
            return
        gather_rate = int(self.workers * 12 * self.blueprint.gather_bonus)
        lumber_rate = int(self.workers * 8 * self.blueprint.gather_bonus)
        food_gain = int(1 + self.workers * 0.2)
        arcana_gain = 1 if self.tech_tier >= 3 else 0
        self.resources.add(gold=gather_rate, lumber=lumber_rate, food=food_gain, arcana=arcana_gain)

    def try_research(self) -> str | None:
        if not self.alive:
            return None
        if self.tech_tier >= len(TECH_TIERS):
            return None
        next_tier = TECH_TIERS[self.tech_tier]
        cost = next_tier["cost"]
        if not self.resources.can_afford(cost):
            return None
        self.resources.spend(cost)
        self.tech_tier += 1
        self.morale = min(1.5, self.morale + 0.05)
        return next_tier["name"]

    def try_train(self) -> int:
        if not self.alive:
            return 0
        if self.supply_used >= self.resources.food:
            return 0
        cost = {"gold": 60, "lumber": 20}
        if not self.resources.can_afford(cost):
            return 0
        self.resources.spend(cost)
        trained = int(1 * self.blueprint.training_bonus)
        self.soldiers += trained
        self.supply_used += trained
        return trained

    def apply_attack(self, attack_strength: float) -> int:
        if not self.alive:
            return 0
        defense = (self.soldiers * 1.6 + self.base_health * 0.3) * self.blueprint.defense_bonus
        net = max(attack_strength - defense, 0)
        losses = int(net / 18)
        self.soldiers = max(self.soldiers - losses, 0)
        self.base_health = max(self.base_health - int(net / 25), 0)
        if self.base_health <= 0 and self.soldiers == 0:
            self.alive = False
        if losses > 0:
            self.morale = max(0.7, self.morale - 0.05)
        return losses


@dataclass
class ZombieAI:
    threat: float = 18.0

    def phase_for_minute(self, minute: int) -> dict:
        phase = ZOMBIE_PHASES[0]
        for entry in ZOMBIE_PHASES:
            if minute >= entry["start"]:
                phase = entry
        return phase

    def generate_attack(self, minute: int, nations_alive: int, rng: Random) -> float:
        phase = self.phase_for_minute(minute)
        variance = rng.uniform(0.85, 1.15)
        scaling = max(1.0, nations_alive * 0.75)
        return self.threat * phase["threat_multiplier"] * variance * scaling


@dataclass
class GameState:
    nations: list[Nation]
    zombie_ai: ZombieAI = field(default_factory=ZombieAI)
    minute: int = 0
    log: list[str] = field(default_factory=list)

    def alive_nations(self) -> list[Nation]:
        return [nation for nation in self.nations if nation.alive]

    def step(self, rng: Random) -> None:
        self.minute += 1
        for nation in self.nations:
            nation.gather_resources()
        for nation in self.nations:
            tier = nation.try_research()
            if tier:
                self.log.append(f"{nation.blueprint.name} reached {tier}.")
            trained = nation.try_train()
            if trained:
                self.log.append(f"{nation.blueprint.name} trained {trained} soldiers.")
        self.resolve_zombie_attack(rng)

    def resolve_zombie_attack(self, rng: Random) -> None:
        alive = self.alive_nations()
        if not alive:
            return
        attack_strength = self.zombie_ai.generate_attack(self.minute, len(alive), rng)
        target = rng.choice(alive)
        losses = target.apply_attack(attack_strength)
        self.log.append(
            f"Zombies hit {target.blueprint.name} for {attack_strength:.1f} threat, "
            f"causing {losses} soldier losses."
        )

    def summary(self) -> str:
        living = self.alive_nations()
        if not living:
            return "All nations have fallen."
        summaries = []
        for nation in living:
            summaries.append(
                f"{nation.blueprint.name}: Tier {nation.tech_tier}, "
                f"Soldiers {nation.soldiers}, Base {nation.base_health}, "
                f"Gold {nation.resources.gold}, Lumber {nation.resources.lumber}, "
                f"Arcana {nation.resources.arcana}"
            )
        return "\n".join(summaries)


def create_default_game() -> GameState:
    nations = [Nation(blueprint=blueprint) for blueprint in NATIONS]
    return GameState(nations=nations)


def simulate_game(ticks: int, seed: int, log_interval: int) -> list[str]:
    rng = Random(seed)
    game = create_default_game()
    output: list[str] = []
    for _ in range(ticks):
        game.step(rng)
        if log_interval and game.minute % log_interval == 0:
            phase = game.zombie_ai.phase_for_minute(game.minute)
            output.append(
                f"\n== Minute {game.minute} ({phase['name']}) ==\n"
                f"{phase['special']}\n{game.summary()}"
            )
        output.extend(game.log)
        game.log.clear()
        if len(game.alive_nations()) <= 1:
            break
    winner = game.alive_nations()
    if winner:
        output.append(f"Winner: {winner[0].blueprint.name}")
    else:
        output.append("The zombies consumed every nation.")
    return output
