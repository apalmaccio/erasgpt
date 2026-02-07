from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import pygame

from .data import NATIONS, ZOMBIE_PHASES

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
UI_HEIGHT = 140
MAP_HEIGHT = SCREEN_HEIGHT - UI_HEIGHT
FPS = 60

COLOR_BG = (18, 16, 22)
COLOR_PANEL = (28, 25, 35)
COLOR_TEXT = (220, 220, 220)
COLOR_ACCENT = (180, 85, 120)
COLOR_ZOMBIE = (75, 150, 110)
COLOR_RESOURCE = (140, 110, 80)
COLOR_LUMBER = (95, 130, 85)
COLOR_SELECTION = (255, 210, 120)

NATION_COLORS = [
    (166, 85, 65),
    (75, 165, 110),
    (90, 110, 150),
    (145, 135, 60),
    (175, 80, 115),
    (165, 120, 75),
    (120, 85, 150),
    (65, 135, 155),
]


@dataclass
class Resources:
    gold: float = 500
    lumber: float = 320
    food: int = 12
    arcana: float = 0


@dataclass
class Unit:
    x: float
    y: float
    unit_type: str
    nation_id: int
    hp: float
    speed: float
    attack: float
    range: float
    cooldown: float
    target: tuple[float, float] | None = None
    cooldown_timer: float = 0.0
    carry_type: str | None = None
    carry_amount: float = 0.0
    task: str = "idle"
    harvest_target: int | None = None

    def update(self, dt: float) -> None:
        if self.target:
            tx, ty = self.target
            dx = tx - self.x
            dy = ty - self.y
            dist = math.hypot(dx, dy)
            if dist > 2:
                self.x += (dx / dist) * self.speed * dt
                self.y += (dy / dist) * self.speed * dt
            else:
                self.target = None
        if self.cooldown_timer > 0:
            self.cooldown_timer = max(self.cooldown_timer - dt, 0)


@dataclass
class Zombie:
    x: float
    y: float
    hp: float = 60
    speed: float = 45
    attack: float = 10
    range: float = 18
    cooldown: float = 1.2
    cooldown_timer: float = 0.0

    def update(self, dt: float, target: tuple[float, float]) -> None:
        tx, ty = target
        dx = tx - self.x
        dy = ty - self.y
        dist = math.hypot(dx, dy)
        if dist > 2:
            self.x += (dx / dist) * self.speed * dt
            self.y += (dy / dist) * self.speed * dt
        if self.cooldown_timer > 0:
            self.cooldown_timer = max(self.cooldown_timer - dt, 0)


@dataclass
class NationState:
    blueprint_name: str
    nation_id: int
    base_pos: tuple[float, float]
    resources: Resources = field(default_factory=Resources)
    base_hp: float = 250
    workers: int = 8
    soldiers: int = 4
    units: list[Unit] = field(default_factory=list)
    buildings: list[tuple[str, tuple[float, float], float]] = field(default_factory=list)
    ai_controlled: bool = True

    def update_food_cap(self) -> None:
        depot_bonus = sum(1 for building in self.buildings if building[0] == "depot") * 6
        self.resources.food = max(self.resources.food, 12 + depot_bonus)

    def can_afford(self, gold: float, lumber: float) -> bool:
        return self.resources.gold >= gold and self.resources.lumber >= lumber

    def spend(self, gold: float, lumber: float) -> None:
        self.resources.gold -= gold
        self.resources.lumber -= lumber


@dataclass
class GameSession:
    nations: list[NationState]
    zombies: list[Zombie]
    selected_unit: Unit | None = None
    selected_nation: int = 0
    minute: float = 0.0
    spawn_timer: float = 0.0
    game_over: bool = False
    winner: str | None = None

    def living_nations(self) -> list[NationState]:
        return [nation for nation in self.nations if nation.base_hp > 0]

    def phase(self) -> dict:
        current = ZOMBIE_PHASES[0]
        for entry in ZOMBIE_PHASES:
            if self.minute >= entry["start"]:
                current = entry
        return current


class GameApp:
    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Eras Zombie Invasion")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 18)
        self.large_font = pygame.font.SysFont("consolas", 24, bold=True)
        self.session = self._create_session()
        self.running = True
        self.resource_nodes = self._create_resource_nodes()
        self.status_message = ""
        self.status_timer = 0.0

    def _create_session(self) -> GameSession:
        nations: list[NationState] = []
        center = (SCREEN_WIDTH / 2, MAP_HEIGHT / 2)
        radius = min(SCREEN_WIDTH, MAP_HEIGHT) * 0.35
        for idx, blueprint in enumerate(NATIONS):
            angle = (idx / len(NATIONS)) * math.tau
            base_x = center[0] + math.cos(angle) * radius
            base_y = center[1] + math.sin(angle) * radius
            nation = NationState(
                blueprint_name=blueprint.name,
                nation_id=idx,
                base_pos=(base_x, base_y),
                ai_controlled=idx != 0,
            )
            for i in range(nation.soldiers):
                offset = 12 * i
                nation.units.append(
                    Unit(
                        x=base_x + offset,
                        y=base_y + 20,
                        unit_type="soldier",
                        nation_id=idx,
                        hp=80,
                        speed=70,
                        attack=18,
                        range=55,
                        cooldown=1.1,
                    )
                )
            for i in range(nation.workers):
                offset = -12 * i
                nation.units.append(
                    Unit(
                        x=base_x + offset,
                        y=base_y - 20,
                        unit_type="worker",
                        nation_id=idx,
                        hp=45,
                        speed=50,
                        attack=4,
                        range=25,
                        cooldown=1.4,
                    )
                )
            nations.append(nation)
        return GameSession(nations=nations, zombies=[])

    def _create_resource_nodes(self) -> list[dict]:
        nodes = []
        rng = random.Random(12)
        for _ in range(12):
            nodes.append(
                {
                    "type": "gold",
                    "x": rng.uniform(100, SCREEN_WIDTH - 100),
                    "y": rng.uniform(80, MAP_HEIGHT - 80),
                    "amount": 2000,
                }
            )
        for _ in range(10):
            nodes.append(
                {
                    "type": "lumber",
                    "x": rng.uniform(120, SCREEN_WIDTH - 120),
                    "y": rng.uniform(80, MAP_HEIGHT - 80),
                    "amount": 1500,
                }
            )
        return nodes

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self._handle_events()
            self._update(dt)
            self._render()
        pygame.quit()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.KEYDOWN:
                if pygame.K_1 <= event.key <= pygame.K_8:
                    self.session.selected_nation = event.key - pygame.K_1
                if event.key == pygame.K_s:
                    self._train_soldier()
                if event.key == pygame.K_w:
                    self._train_worker()
                if event.key == pygame.K_d:
                    self._build_depot()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    self._select_unit(event.pos)
                if event.button == 3:
                    self._move_selected(event.pos)

    def _select_unit(self, pos: tuple[int, int]) -> None:
        x, y = pos
        selected = None
        for unit in self._units_for_nation(self.session.selected_nation):
            if math.hypot(unit.x - x, unit.y - y) < 16:
                selected = unit
                break
        self.session.selected_unit = selected

    def _move_selected(self, pos: tuple[int, int]) -> None:
        if self.session.selected_unit:
            self.session.selected_unit.target = (float(pos[0]), float(pos[1]))

    def _train_soldier(self) -> None:
        nation = self.session.nations[self.session.selected_nation]
        if nation.workers + nation.soldiers >= nation.resources.food:
            self._set_status("Supply cap reached.")
            return
        if not nation.can_afford(90, 30):
            return
        nation.spend(90, 30)
        nation.soldiers += 1
        base_x, base_y = nation.base_pos
        nation.units.append(
            Unit(
                x=base_x + random.uniform(-25, 25),
                y=base_y + random.uniform(-25, 25),
                unit_type="soldier",
                nation_id=nation.nation_id,
                hp=80,
                speed=70,
                attack=18,
                range=55,
                cooldown=1.1,
            )
        )
        self._set_status("Trained soldier.")

    def _train_worker(self) -> None:
        nation = self.session.nations[self.session.selected_nation]
        if nation.workers + nation.soldiers >= nation.resources.food:
            self._set_status("Supply cap reached.")
            return
        if not nation.can_afford(50, 15):
            return
        nation.spend(50, 15)
        nation.workers += 1
        base_x, base_y = nation.base_pos
        nation.units.append(
            Unit(
                x=base_x + random.uniform(-20, 20),
                y=base_y + random.uniform(-20, 20),
                unit_type="worker",
                nation_id=nation.nation_id,
                hp=45,
                speed=50,
                attack=4,
                range=25,
                cooldown=1.4,
            )
        )
        self._set_status("Trained worker.")

    def _build_depot(self) -> None:
        nation = self.session.nations[self.session.selected_nation]
        if not nation.can_afford(140, 60):
            self._set_status("Not enough resources for depot.")
            return
        nation.spend(140, 60)
        base_x, base_y = nation.base_pos
        offset = random.uniform(-35, 35)
        pos = (base_x + offset, base_y + offset)
        nation.buildings.append(("depot", pos, 180))
        nation.update_food_cap()
        self._set_status("Built supply depot.")

    def _units_for_nation(self, nation_id: int) -> list[Unit]:
        return self.session.nations[nation_id].units

    def _update(self, dt: float) -> None:
        session = self.session
        if session.game_over:
            return
        session.minute += dt / 60
        self._spawn_zombies(dt)
        for idx, nation in enumerate(session.nations):
            if nation.base_hp <= 0:
                continue
            nation.update_food_cap()
            gather_bonus = NATIONS[idx].gather_bonus
            if nation.ai_controlled:
                self._ai_take_turn(nation, dt)
            for unit in list(nation.units):
                unit.update(dt)
            self._update_worker_tasks(nation, gather_bonus, dt)
        self._update_zombies(dt)
        self._resolve_combat(dt)
        self._check_victory()
        if self.status_timer > 0:
            self.status_timer = max(0.0, self.status_timer - dt)

    def _ai_take_turn(self, nation: NationState, dt: float) -> None:
        if (
            nation.can_afford(90, 30)
            and nation.soldiers < 14
            and nation.workers + nation.soldiers < nation.resources.food
        ):
            nation.spend(90, 30)
            nation.soldiers += 1
            base_x, base_y = nation.base_pos
            nation.units.append(
                Unit(
                    x=base_x + random.uniform(-25, 25),
                    y=base_y + random.uniform(-25, 25),
                    unit_type="soldier",
                    nation_id=nation.nation_id,
                    hp=80,
                    speed=70,
                    attack=18,
                    range=55,
                    cooldown=1.1,
                )
            )
        if (
            nation.can_afford(50, 15)
            and nation.workers < 12
            and nation.workers + nation.soldiers < nation.resources.food
        ):
            nation.spend(50, 15)
            nation.workers += 1
            base_x, base_y = nation.base_pos
            nation.units.append(
                Unit(
                    x=base_x + random.uniform(-20, 20),
                    y=base_y + random.uniform(-20, 20),
                    unit_type="worker",
                    nation_id=nation.nation_id,
                    hp=45,
                    speed=50,
                    attack=4,
                    range=25,
                    cooldown=1.4,
                )
            )
        if nation.can_afford(140, 60) and len(nation.buildings) < 3:
            nation.spend(140, 60)
            base_x, base_y = nation.base_pos
            offset = random.uniform(-35, 35)
            nation.buildings.append(("depot", (base_x + offset, base_y + offset), 180))
            nation.update_food_cap()
        for unit in nation.units:
            if unit.unit_type == "soldier" and unit.target is None:
                offset = random.uniform(-40, 40)
                unit.target = (
                    nation.base_pos[0] + offset,
                    nation.base_pos[1] + offset,
                )

    def _spawn_zombies(self, dt: float) -> None:
        session = self.session
        phase = session.phase()
        session.spawn_timer += dt
        spawn_interval = max(1.8, 4.5 - phase["threat_multiplier"])
        if session.spawn_timer < spawn_interval:
            return
        session.spawn_timer = 0
        count = int(2 + phase["threat_multiplier"] * 2)
        for _ in range(count):
            edge = random.choice(["top", "bottom", "left", "right"])
            if edge == "top":
                x, y = random.uniform(0, SCREEN_WIDTH), random.uniform(10, 50)
            elif edge == "bottom":
                x, y = random.uniform(0, SCREEN_WIDTH), random.uniform(MAP_HEIGHT - 50, MAP_HEIGHT - 10)
            elif edge == "left":
                x, y = random.uniform(10, 50), random.uniform(0, MAP_HEIGHT)
            else:
                x, y = random.uniform(SCREEN_WIDTH - 50, SCREEN_WIDTH - 10), random.uniform(0, MAP_HEIGHT)
            session.zombies.append(Zombie(x=x, y=y))

    def _update_worker_tasks(self, nation: NationState, gather_bonus: float, dt: float) -> None:
        for unit in nation.units:
            if unit.unit_type != "worker":
                continue
            if unit.task == "idle":
                node_index = self._find_closest_node(unit.x, unit.y)
                if node_index is not None:
                    unit.harvest_target = node_index
                    unit.target = (self.resource_nodes[node_index]["x"], self.resource_nodes[node_index]["y"])
                    unit.task = "gather"
            elif unit.task == "gather":
                if unit.harvest_target is None:
                    unit.task = "idle"
                    continue
                node = self.resource_nodes[unit.harvest_target]
                if node["amount"] <= 0:
                    unit.task = "idle"
                    unit.harvest_target = None
                    continue
                if self._distance((unit.x, unit.y), (node["x"], node["y"])) < 18:
                    harvest = 8 * gather_bonus * dt
                    node["amount"] = max(0, node["amount"] - harvest)
                    unit.carry_type = node["type"]
                    unit.carry_amount += harvest
                    if unit.carry_amount >= 20:
                        unit.task = "return"
                        unit.target = nation.base_pos
            elif unit.task == "return":
                if self._distance((unit.x, unit.y), nation.base_pos) < 20:
                    if unit.carry_type == "gold":
                        nation.resources.gold += unit.carry_amount
                    elif unit.carry_type == "lumber":
                        nation.resources.lumber += unit.carry_amount
                    unit.carry_amount = 0
                    unit.carry_type = None
                    unit.task = "idle"

    def _find_closest_node(self, x: float, y: float) -> int | None:
        best_index = None
        best_dist = float("inf")
        for idx, node in enumerate(self.resource_nodes):
            if node["amount"] <= 0:
                continue
            dist = self._distance((x, y), (node["x"], node["y"]))
            if dist < best_dist:
                best_dist = dist
                best_index = idx
        return best_index

    def _update_zombies(self, dt: float) -> None:
        session = self.session
        living = session.living_nations()
        if not living:
            return
        for zombie in list(session.zombies):
            target_nation = min(living, key=lambda n: self._distance((zombie.x, zombie.y), n.base_pos))
            zombie.update(dt, target_nation.base_pos)

    def _resolve_combat(self, dt: float) -> None:
        session = self.session
        for nation in session.nations:
            for unit in list(nation.units):
                if unit.cooldown_timer > 0:
                    continue
                target = self._closest_zombie(unit.x, unit.y, unit.range)
                if target:
                    target.hp -= unit.attack
                    unit.cooldown_timer = unit.cooldown
        for zombie in list(session.zombies):
            if zombie.cooldown_timer > 0:
                continue
            target_unit = self._closest_unit(zombie.x, zombie.y, zombie.range)
            if target_unit:
                target_unit.hp -= zombie.attack
                zombie.cooldown_timer = zombie.cooldown
        for nation in session.nations:
            for unit in list(nation.units):
                if unit.hp <= 0:
                    nation.units.remove(unit)
                    if unit.unit_type == "worker":
                        nation.workers = max(0, nation.workers - 1)
                    else:
                        nation.soldiers = max(0, nation.soldiers - 1)
        for zombie in list(session.zombies):
            if zombie.hp <= 0:
                session.zombies.remove(zombie)
        for nation in session.nations:
            for zombie in list(session.zombies):
                if self._distance((zombie.x, zombie.y), nation.base_pos) < 22:
                    nation.base_hp = max(0, nation.base_hp - zombie.attack * dt)
            for building in list(nation.buildings):
                if building[0] == "depot":
                    for zombie in list(session.zombies):
                        if self._distance((zombie.x, zombie.y), building[1]) < 18:
                            new_hp = max(0, building[2] - zombie.attack * dt)
                            nation.buildings.remove(building)
                            if new_hp > 0:
                                nation.buildings.append((building[0], building[1], new_hp))
                            else:
                                nation.update_food_cap()
                            break

    def _check_victory(self) -> None:
        living = self.session.living_nations()
        if len(living) <= 1:
            self.session.game_over = True
            if living:
                self.session.winner = living[0].blueprint_name
            else:
                self.session.winner = "Zombies"

    def _closest_zombie(self, x: float, y: float, radius: float) -> Zombie | None:
        closest = None
        closest_dist = radius
        for zombie in self.session.zombies:
            dist = self._distance((x, y), (zombie.x, zombie.y))
            if dist < closest_dist:
                closest_dist = dist
                closest = zombie
        return closest

    def _closest_unit(self, x: float, y: float, radius: float) -> Unit | None:
        closest = None
        closest_dist = radius
        for nation in self.session.nations:
            for unit in nation.units:
                dist = self._distance((x, y), (unit.x, unit.y))
                if dist < closest_dist:
                    closest_dist = dist
                    closest = unit
        return closest

    @staticmethod
    def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def _render(self) -> None:
        self.screen.fill(COLOR_BG)
        pygame.draw.rect(self.screen, COLOR_PANEL, (0, MAP_HEIGHT, SCREEN_WIDTH, UI_HEIGHT))
        self._draw_map()
        self._draw_ui()
        pygame.display.flip()

    def _draw_map(self) -> None:
        for node in self.resource_nodes:
            if node["amount"] <= 0:
                continue
            color = COLOR_RESOURCE if node["type"] == "gold" else COLOR_LUMBER
            pygame.draw.circle(self.screen, color, (int(node["x"]), int(node["y"])), 10)
        for idx, nation in enumerate(self.session.nations):
            if nation.base_hp <= 0:
                continue
            color = NATION_COLORS[idx]
            base_x, base_y = nation.base_pos
            pygame.draw.circle(self.screen, color, (int(base_x), int(base_y)), 20)
            pygame.draw.circle(self.screen, COLOR_ACCENT, (int(base_x), int(base_y)), 24, 2)
            for building in nation.buildings:
                if building[0] == "depot":
                    pygame.draw.rect(
                        self.screen,
                        COLOR_ACCENT,
                        pygame.Rect(building[1][0] - 10, building[1][1] - 10, 20, 20),
                        border_radius=2,
                    )
            for unit in nation.units:
                radius = 6 if unit.unit_type == "worker" else 8
                pygame.draw.circle(self.screen, color, (int(unit.x), int(unit.y)), radius)
                if unit is self.session.selected_unit:
                    pygame.draw.circle(
                        self.screen,
                        COLOR_SELECTION,
                        (int(unit.x), int(unit.y)),
                        radius + 4,
                        2,
                    )
        for zombie in self.session.zombies:
            pygame.draw.circle(self.screen, COLOR_ZOMBIE, (int(zombie.x), int(zombie.y)), 8)

    def _draw_ui(self) -> None:
        nation = self.session.nations[self.session.selected_nation]
        phase = self.session.phase()
        header = f"Nation {self.session.selected_nation + 1}: {nation.blueprint_name}"
        self._blit_text(header, 20, MAP_HEIGHT + 12, self.large_font)
        stats = (
            f"Gold {nation.resources.gold:,.0f}  Lumber {nation.resources.lumber:,.0f}  "
            f"Workers {nation.workers}  Soldiers {nation.soldiers}  Base {nation.base_hp:,.0f}  "
            f"Food {nation.workers + nation.soldiers}/{nation.resources.food}"
        )
        self._blit_text(stats, 20, MAP_HEIGHT + 44, self.font)
        phase_text = f"Zombie Phase: {phase['name']}"
        self._blit_text(phase_text, 20, MAP_HEIGHT + 70, self.font)
        controls = "Controls: 1-8 switch nation | LMB select | RMB move | S soldier | W worker | D depot"
        self._blit_text(controls, 20, MAP_HEIGHT + 96, self.font)
        living = len(self.session.living_nations())
        status = f"Zombies: {len(self.session.zombies)} | Nations Standing: {living}"
        self._blit_text(status, 800, MAP_HEIGHT + 44, self.font)
        if self.status_timer > 0:
            self._blit_text(self.status_message, 800, MAP_HEIGHT + 70, self.font)
        if self.session.game_over:
            winner = self.session.winner or "None"
            end_text = f"Game Over - Winner: {winner}"
            self._blit_text(end_text, 800, MAP_HEIGHT + 96, self.large_font)

    def _set_status(self, message: str) -> None:
        self.status_message = message
        self.status_timer = 3.0

    def _blit_text(self, text: str, x: int, y: int, font: pygame.font.Font) -> None:
        surface = font.render(text, True, COLOR_TEXT)
        self.screen.blit(surface, (x, y))


def main() -> None:
    app = GameApp()
    app.run()


if __name__ == "__main__":
    main()
