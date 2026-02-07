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
COLOR_GOLD = (200, 170, 90)
COLOR_LUMBER = (110, 140, 90)
COLOR_TOWER = (120, 100, 160)
COLOR_BARRACKS = (120, 70, 55)
COLOR_ALERT = (200, 80, 80)
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
    harvest_node_id: int | None = None
    cooldown_timer: float = 0.0

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
    ai_controlled: bool = True
    tech_tier: int = 1
    buildings: list["Building"] = field(default_factory=list)

    def gather(self, dt: float, gather_bonus: float) -> None:
        gold_rate = self.workers * 2.2 * gather_bonus
        lumber_rate = self.workers * 1.6 * gather_bonus
        self.resources.gold += gold_rate * dt
        self.resources.lumber += lumber_rate * dt
        self.resources.food = max(self.resources.food, self.workers + self.soldiers + 4)

    def can_afford(self, gold: float, lumber: float) -> bool:
        return self.resources.gold >= gold and self.resources.lumber >= lumber

    def spend(self, gold: float, lumber: float) -> None:
        self.resources.gold -= gold
        self.resources.lumber -= lumber


@dataclass
class ResourceNode:
    node_id: int
    x: float
    y: float
    kind: str
    amount: float = 1200


@dataclass
class Building:
    x: float
    y: float
    building_type: str
    hp: float
    nation_id: int
    cooldown_timer: float = 0.0


@dataclass
class GameSession:
    nations: list[NationState]
    zombies: list[Zombie]
    nodes: list[ResourceNode]
    selected_unit: Unit | None = None
    selected_nation: int = 0
    minute: float = 0.0
    spawn_timer: float = 0.0
    build_mode: str | None = None
    messages: list[str] = field(default_factory=list)
    game_over: bool = False

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

    def _create_session(self) -> GameSession:
        nations: list[NationState] = []
        nodes: list[ResourceNode] = []
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
            nation.buildings.append(
                Building(x=base_x, y=base_y, building_type="base", hp=250, nation_id=idx)
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
        node_id = 0
        for ring in (0.2, 0.45, 0.6):
            ring_radius = min(SCREEN_WIDTH, MAP_HEIGHT) * ring
            for i in range(8):
                angle = (i / 8) * math.tau + ring
                x = center[0] + math.cos(angle) * ring_radius
                y = center[1] + math.sin(angle) * ring_radius
                kind = "gold" if i % 2 == 0 else "lumber"
                nodes.append(ResourceNode(node_id=node_id, x=x, y=y, kind=kind))
                node_id += 1
        return GameSession(nations=nations, zombies=[], nodes=nodes)

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
                    self.session.build_mode = None
                if event.key == pygame.K_s:
                    self._train_soldier()
                if event.key == pygame.K_w:
                    self._train_worker()
                if event.key == pygame.K_r:
                    self._research_tier()
                if event.key == pygame.K_b:
                    self.session.build_mode = "barracks"
                if event.key == pygame.K_d:
                    self.session.build_mode = "tower"
                if event.key == pygame.K_ESCAPE:
                    if self.session.game_over:
                        self.running = False
                    self.session.build_mode = None
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if self.session.build_mode:
                        self._place_building(event.pos)
                    else:
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
            node = self._node_at_position(pos)
            if node and self.session.selected_unit.unit_type == "worker":
                self.session.selected_unit.harvest_node_id = node.node_id
                self.session.selected_unit.target = (node.x, node.y)
            else:
                self.session.selected_unit.harvest_node_id = None
                self.session.selected_unit.target = (float(pos[0]), float(pos[1]))

    def _place_building(self, pos: tuple[int, int]) -> None:
        nation = self.session.nations[self.session.selected_nation]
        if nation.base_hp <= 0:
            return
        if self.session.build_mode == "barracks":
            cost = (140, 80)
            building_type = "barracks"
            hp = 180
        else:
            cost = (120, 100)
            building_type = "tower"
            hp = 160
        if not nation.can_afford(*cost):
            self._push_message("Not enough resources.")
            return
        if self._too_close_to_base(pos, nation.base_pos) or self._building_at_position(pos):
            self._push_message("Placement blocked.")
            return
        nation.spend(*cost)
        nation.buildings.append(
            Building(
                x=float(pos[0]),
                y=float(pos[1]),
                building_type=building_type,
                hp=hp,
                nation_id=nation.nation_id,
            )
        )
        self._push_message(f"{building_type.title()} constructed.")
        self.session.build_mode = None

    def _train_soldier(self) -> None:
        nation = self.session.nations[self.session.selected_nation]
        if not any(building.building_type == "barracks" for building in nation.buildings):
            self._push_message("Build a barracks to train soldiers.")
            return
        if not nation.can_afford(90, 30):
            self._push_message("Not enough resources.")
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

    def _train_worker(self) -> None:
        nation = self.session.nations[self.session.selected_nation]
        if not nation.can_afford(50, 15):
            self._push_message("Not enough resources.")
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

    def _research_tier(self) -> None:
        nation = self.session.nations[self.session.selected_nation]
        if nation.tech_tier >= 4:
            self._push_message("Tech tree fully researched.")
            return
        costs = {
            1: (280, 180),
            2: (520, 360),
            3: (820, 520),
        }
        gold, lumber = costs.get(nation.tech_tier, (0, 0))
        if not nation.can_afford(gold, lumber):
            self._push_message("Not enough resources.")
            return
        nation.spend(gold, lumber)
        nation.tech_tier += 1
        self._push_message(f"Tech Tier {nation.tech_tier} reached.")

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
            gather_bonus = NATIONS[idx].gather_bonus
            nation.gather(dt, gather_bonus)
            if nation.ai_controlled:
                self._ai_take_turn(nation, dt)
            for unit in list(nation.units):
                unit.update(dt)
            self._harvest_with_workers(nation, dt)
            self._update_buildings(nation, dt)
        self._update_zombies(dt)
        self._resolve_combat(dt)
        self._cleanup_destroyed()
        self._check_game_over()

    def _ai_take_turn(self, nation: NationState, dt: float) -> None:
        has_barracks = any(building.building_type == "barracks" for building in nation.buildings)
        if has_barracks and nation.can_afford(90, 30) and nation.soldiers < 14:
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
        if nation.can_afford(50, 15) and nation.workers < 12:
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
        for unit in nation.units:
            if unit.unit_type == "soldier" and unit.target is None:
                offset = random.uniform(-40, 40)
                unit.target = (
                    nation.base_pos[0] + offset,
                    nation.base_pos[1] + offset,
                )
        if nation.tech_tier < 3 and nation.can_afford(320, 220):
            nation.spend(320, 220)
            nation.tech_tier += 1
        if not any(building.building_type == "barracks" for building in nation.buildings):
            if nation.can_afford(140, 80):
                nation.spend(140, 80)
                base_x, base_y = nation.base_pos
                nation.buildings.append(
                    Building(
                        x=base_x + random.uniform(-60, 60),
                        y=base_y + random.uniform(-60, 60),
                        building_type="barracks",
                        hp=180,
                        nation_id=nation.nation_id,
                    )
                )
        if nation.can_afford(120, 100) and len(nation.buildings) < 3:
            base_x, base_y = nation.base_pos
            nation.spend(120, 100)
            nation.buildings.append(
                Building(
                    x=base_x + random.uniform(-90, 90),
                    y=base_y + random.uniform(-90, 90),
                    building_type="tower",
                    hp=160,
                    nation_id=nation.nation_id,
                )
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
                continue
            target_building = self._closest_building(zombie.x, zombie.y, zombie.range)
            if target_building:
                target_building.hp -= zombie.attack
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
                    if nation.base_hp == 0:
                        self._push_message(f"{nation.blueprint_name} has fallen.")

    def _harvest_with_workers(self, nation: NationState, dt: float) -> None:
        for unit in nation.units:
            if unit.unit_type != "worker" or unit.harvest_node_id is None:
                continue
            node = next((n for n in self.session.nodes if n.node_id == unit.harvest_node_id), None)
            if not node or node.amount <= 0:
                unit.harvest_node_id = None
                continue
            if self._distance((unit.x, unit.y), (node.x, node.y)) < 22:
                gathered = min(node.amount, 6 * dt)
                node.amount -= gathered
                if node.kind == "gold":
                    nation.resources.gold += gathered
                else:
                    nation.resources.lumber += gathered

    def _update_buildings(self, nation: NationState, dt: float) -> None:
        for building in nation.buildings:
            if building.cooldown_timer > 0:
                building.cooldown_timer = max(building.cooldown_timer - dt, 0)
            if building.building_type != "tower" or building.cooldown_timer > 0:
                continue
            target = self._closest_zombie(building.x, building.y, 140)
            if target:
                target.hp -= 12 + nation.tech_tier * 3
                building.cooldown_timer = 1.2

    def _cleanup_destroyed(self) -> None:
        for nation in self.session.nations:
            for building in list(nation.buildings):
                if building.hp <= 0 and building.building_type != "base":
                    nation.buildings.remove(building)
        for node in list(self.session.nodes):
            if node.amount <= 0:
                self.session.nodes.remove(node)

    def _check_game_over(self) -> None:
        living = self.session.living_nations()
        if len(living) <= 1:
            self.session.game_over = True

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

    def _closest_building(self, x: float, y: float, radius: float) -> Building | None:
        closest = None
        closest_dist = radius
        for nation in self.session.nations:
            for building in nation.buildings:
                dist = self._distance((x, y), (building.x, building.y))
                if dist < closest_dist:
                    closest_dist = dist
                    closest = building
        return closest

    @staticmethod
    def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def _render(self) -> None:
        self.screen.fill(COLOR_BG)
        pygame.draw.rect(self.screen, COLOR_PANEL, (0, MAP_HEIGHT, SCREEN_WIDTH, UI_HEIGHT))
        self._draw_map()
        self._draw_ui()
        if self.session.game_over:
            self._draw_game_over()
        pygame.display.flip()

    def _draw_map(self) -> None:
        for node in self.session.nodes:
            color = COLOR_GOLD if node.kind == "gold" else COLOR_LUMBER
            pygame.draw.circle(self.screen, color, (int(node.x), int(node.y)), 10)
        for idx, nation in enumerate(self.session.nations):
            if nation.base_hp <= 0:
                continue
            color = NATION_COLORS[idx]
            base_x, base_y = nation.base_pos
            pygame.draw.circle(self.screen, color, (int(base_x), int(base_y)), 20)
            pygame.draw.circle(self.screen, COLOR_ACCENT, (int(base_x), int(base_y)), 24, 2)
            for building in nation.buildings:
                if building.building_type == "barracks":
                    rect = pygame.Rect(0, 0, 24, 24)
                    rect.center = (building.x, building.y)
                    pygame.draw.rect(self.screen, COLOR_BARRACKS, rect)
                elif building.building_type == "tower":
                    pygame.draw.circle(
                        self.screen,
                        COLOR_TOWER,
                        (int(building.x), int(building.y)),
                        12,
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
            f"Workers {nation.workers}  Soldiers {nation.soldiers}  "
            f"Base {nation.base_hp:,.0f}  Tier {nation.tech_tier}"
        )
        self._blit_text(stats, 20, MAP_HEIGHT + 44, self.font)
        phase_text = f"Zombie Phase: {phase['name']}"
        self._blit_text(phase_text, 20, MAP_HEIGHT + 70, self.font)
        controls = (
            "Controls: 1-8 switch | LMB select/place | RMB move/harvest | "
            "S soldier | W worker | R tech | B barracks | D tower | Esc cancel"
        )
        self._blit_text(controls, 20, MAP_HEIGHT + 96, self.font)
        living = len(self.session.living_nations())
        status = f"Zombies: {len(self.session.zombies)} | Nations Standing: {living}"
        self._blit_text(status, 800, MAP_HEIGHT + 44, self.font)
        if self.session.build_mode:
            self._blit_text(
                f"Build Mode: {self.session.build_mode.title()}",
                800,
                MAP_HEIGHT + 70,
                self.font,
                color=COLOR_ALERT,
            )
        self._draw_messages()

    def _draw_game_over(self) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, MAP_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 10, 12, 210))
        self.screen.blit(overlay, (0, 0))
        living = self.session.living_nations()
        message = "Zombies consumed the realm." if not living else f"{living[0].blueprint_name} wins!"
        self._blit_text(message, 420, MAP_HEIGHT / 2 - 20, self.large_font)
        self._blit_text("Press Esc to exit.", 470, MAP_HEIGHT / 2 + 10, self.font)

    def _draw_messages(self) -> None:
        base_y = MAP_HEIGHT + 10
        for idx, message in enumerate(self.session.messages[-3:]):
            self._blit_text(message, 800, base_y + idx * 20, self.font, color=COLOR_ALERT)

    def _blit_text(
        self, text: str, x: float, y: float, font: pygame.font.Font, color: tuple[int, int, int] = COLOR_TEXT
    ) -> None:
        surface = font.render(text, True, color)
        self.screen.blit(surface, (x, y))

    def _push_message(self, message: str) -> None:
        self.session.messages.append(message)

    def _node_at_position(self, pos: tuple[int, int]) -> ResourceNode | None:
        for node in self.session.nodes:
            if self._distance(pos, (node.x, node.y)) < 16:
                return node
        return None

    def _building_at_position(self, pos: tuple[int, int]) -> bool:
        for nation in self.session.nations:
            for building in nation.buildings:
                if self._distance(pos, (building.x, building.y)) < 20:
                    return True
        return False

    @staticmethod
    def _too_close_to_base(pos: tuple[int, int], base: tuple[float, float]) -> bool:
        return math.hypot(pos[0] - base[0], pos[1] - base[1]) < 40


def main() -> None:
    app = GameApp()
    app.run()


if __name__ == "__main__":
    main()
