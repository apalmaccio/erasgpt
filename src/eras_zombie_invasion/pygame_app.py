from __future__ import annotations

import math
import os
import random
from array import array
from dataclasses import dataclass, field

import pygame

from .data import NATIONS, ZOMBIE_PHASES

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
UI_HEIGHT = 170
MAP_HEIGHT = SCREEN_HEIGHT - UI_HEIGHT
FPS = 60

COLOR_BG = (16, 14, 22)
COLOR_PANEL = (28, 25, 35)
COLOR_TEXT = (220, 220, 220)
COLOR_ACCENT = (180, 85, 120)
COLOR_ZOMBIE = (75, 150, 110)
COLOR_ZOMBIE_FAST = (110, 170, 110)
COLOR_ZOMBIE_BRUTE = (90, 110, 130)
COLOR_ZOMBIE_BOSS = (150, 90, 110)
COLOR_RESOURCE = (140, 110, 80)
COLOR_GOLD = (200, 170, 90)
COLOR_LUMBER = (110, 140, 90)
COLOR_TOWER = (120, 100, 160)
COLOR_BARRACKS = (120, 70, 55)
COLOR_ALERT = (200, 80, 80)
COLOR_SELECTION = (255, 210, 120)
COLOR_GRID = (32, 30, 38)
COLOR_WATER = (20, 35, 55)
COLOR_HIGHLIGHT = (255, 235, 160)

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

ZOMBIE_VARIANTS = {
    "shambler": {
        "hp": 60,
        "speed": 42,
        "attack": 10,
        "range": 18,
        "cooldown": 1.2,
        "size": 8,
        "color": COLOR_ZOMBIE,
    },
    "runner": {
        "hp": 45,
        "speed": 85,
        "attack": 8,
        "range": 18,
        "cooldown": 0.9,
        "size": 7,
        "color": COLOR_ZOMBIE_FAST,
    },
    "brute": {
        "hp": 150,
        "speed": 30,
        "attack": 22,
        "range": 22,
        "cooldown": 1.6,
        "size": 12,
        "color": COLOR_ZOMBIE_BRUTE,
    },
    "spitter": {
        "hp": 70,
        "speed": 34,
        "attack": 12,
        "range": 80,
        "cooldown": 1.8,
        "size": 9,
        "color": (100, 190, 130),
    },
    "boss": {
        "hp": 420,
        "speed": 26,
        "attack": 32,
        "range": 28,
        "cooldown": 1.5,
        "size": 18,
        "color": COLOR_ZOMBIE_BOSS,
    },
}


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
    buff_timer: float = 0.0
    level: int = 1
    xp: float = 0.0

    def update(self, dt: float) -> None:
        if self.target:
            tx, ty = self.target
            dx = tx - self.x
            dy = ty - self.y
            dist = math.hypot(dx, dy)
            if dist > 2:
                self.x += (dx / dist) * self.current_speed * dt
                self.y += (dy / dist) * self.current_speed * dt
            else:
                self.target = None
        if self.cooldown_timer > 0:
            self.cooldown_timer = max(self.cooldown_timer - dt, 0)
        if self.buff_timer > 0:
            self.buff_timer = max(self.buff_timer - dt, 0)

    @property
    def current_speed(self) -> float:
        return self.speed * (1.25 if self.buff_timer > 0 else 1.0)

    @property
    def current_attack(self) -> float:
        return self.attack * (1.35 if self.buff_timer > 0 else 1.0)


@dataclass
class Zombie:
    x: float
    y: float
    kind: str = "shambler"
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
    base_max_hp: float = 250
    workers: int = 8
    soldiers: int = 4
    units: list[Unit] = field(default_factory=list)
    ai_controlled: bool = True
    tech_tier: int = 1
    buildings: list["Building"] = field(default_factory=list)
    hero_cooldown: float = 0.0

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

    def supply_cap(self) -> int:
        barracks = sum(1 for building in self.buildings if building.building_type == "barracks")
        towers = sum(1 for building in self.buildings if building.building_type == "tower")
        return 12 + barracks * 4 + towers * 2

    def supply_used(self) -> int:
        return self.workers + self.soldiers + sum(1 for unit in self.units if unit.unit_type == "hero") * 2


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
    max_hp: float
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
    victory: bool = False
    zombies_slain: int = 0
    objective_minutes: float = 18
    objective_kills: int = 220
    paused: bool = False
    last_spawn_sound: float = 0.0

    def living_nations(self) -> list[NationState]:
        return [nation for nation in self.nations if nation.base_hp > 0]

    def phase(self) -> dict:
        current = ZOMBIE_PHASES[0]
        for entry in ZOMBIE_PHASES:
            if self.minute >= entry["start"]:
                current = entry
        return current


class AudioManager:
    def __init__(self) -> None:
        self.enabled = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.music: pygame.mixer.Sound | None = None
        self.music_channel: pygame.mixer.Channel | None = None
        try:
            pygame.mixer.init()
        except pygame.error:
            return
        self.enabled = True
        self._build_sounds()

    def _build_sounds(self) -> None:
        self.sounds["place"] = self._tone(520, 0.16, 0.35)
        self.sounds["train"] = self._tone(430, 0.18, 0.3, decay=2.6)
        self.sounds["warning"] = self._tone(240, 0.22, 0.38, decay=2.4)
        self.sounds["spawn"] = self._tone(120, 0.35, 0.5, decay=1.4)
        self.sounds["victory"] = self._chord([440, 550, 660], 0.8, 0.45)
        self.sounds["defeat"] = self._tone(170, 0.9, 0.5, decay=1.1)
        self.sounds["buff"] = self._chord([620, 740], 0.35, 0.4, decay=1.8)
        self.music = self._music_loop()

    def _tone(self, freq: float, duration: float, volume: float, decay: float = 0.0) -> pygame.mixer.Sound:
        sample_rate = 44100
        count = int(sample_rate * duration)
        samples = array("h")
        for i in range(count):
            t = i / sample_rate
            amp = math.sin(2 * math.pi * freq * t)
            if decay:
                amp *= math.exp(-decay * t)
            samples.append(int(amp * volume * 32767))
        return pygame.mixer.Sound(buffer=samples)

    def _chord(
        self, freqs: list[float], duration: float, volume: float, decay: float = 0.0
    ) -> pygame.mixer.Sound:
        sample_rate = 44100
        count = int(sample_rate * duration)
        samples = array("h")
        for i in range(count):
            t = i / sample_rate
            amp = sum(math.sin(2 * math.pi * freq * t) for freq in freqs) / len(freqs)
            if decay:
                amp *= math.exp(-decay * t)
            samples.append(int(amp * volume * 32767))
        return pygame.mixer.Sound(buffer=samples)

    def _music_loop(self) -> pygame.mixer.Sound:
        sample_rate = 44100
        duration = 10.0
        count = int(sample_rate * duration)
        samples = array("h")
        chords = [
            [220, 277, 330],
            [196, 247, 294],
            [174, 220, 262],
            [207, 262, 311],
        ]
        for i in range(count):
            t = i / sample_rate
            chord = chords[int(t // 2.5) % len(chords)]
            amp = sum(math.sin(2 * math.pi * freq * t) for freq in chord) / len(chord)
            amp *= 0.25 + 0.05 * math.sin(2 * math.pi * 0.5 * t)
            samples.append(int(amp * 32767))
        return pygame.mixer.Sound(buffer=samples)

    def play(self, name: str) -> None:
        if not self.enabled:
            return
        sound = self.sounds.get(name)
        if sound:
            sound.play()

    def play_music(self) -> None:
        if not self.enabled or not self.music:
            return
        if not self.music_channel or not self.music_channel.get_busy():
            self.music_channel = self.music.play(loops=-1)

    def toggle_music(self) -> None:
        if not self.enabled:
            return
        if self.music_channel and self.music_channel.get_busy():
            self.music_channel.stop()
        else:
            self.play_music()


class GameApp:
    def __init__(self) -> None:
        pygame.mixer.pre_init(44100, -16, 1, 512)
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Eras Zombie Invasion")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 18)
        self.large_font = pygame.font.SysFont("consolas", 24, bold=True)
        self.session = self._create_session()
        self.running = True
        self.audio = AudioManager()
        self.audio.play_music()
        self.background = self._generate_background()

    def _generate_background(self) -> pygame.Surface:
        surface = pygame.Surface((SCREEN_WIDTH, MAP_HEIGHT))
        surface.fill(COLOR_BG)
        for x in range(0, SCREEN_WIDTH, 40):
            pygame.draw.line(surface, COLOR_GRID, (x, 0), (x, MAP_HEIGHT))
        for y in range(0, MAP_HEIGHT, 40):
            pygame.draw.line(surface, COLOR_GRID, (0, y), (SCREEN_WIDTH, y))
        pygame.draw.circle(surface, COLOR_WATER, (SCREEN_WIDTH // 2, MAP_HEIGHT // 2), 180, 4)
        return surface

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
                Building(
                    x=base_x,
                    y=base_y,
                    building_type="base",
                    hp=250,
                    max_hp=250,
                    nation_id=idx,
                )
            )
            for i in range(nation.soldiers):
                offset = 14 * i
                nation.units.append(
                    Unit(
                        x=base_x + offset,
                        y=base_y + 25,
                        unit_type="soldier",
                        nation_id=idx,
                        hp=90,
                        speed=72,
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
                        y=base_y - 25,
                        unit_type="worker",
                        nation_id=idx,
                        hp=55,
                        speed=55,
                        attack=4,
                        range=25,
                        cooldown=1.4,
                    )
                )
            if idx == 0:
                nation.units.append(
                    Unit(
                        x=base_x + 20,
                        y=base_y,
                        unit_type="hero",
                        nation_id=idx,
                        hp=220,
                        speed=82,
                        attack=26,
                        range=65,
                        cooldown=0.9,
                    )
                )
            nations.append(nation)
        node_id = 0
        for ring in (0.2, 0.45, 0.6):
            ring_radius = min(SCREEN_WIDTH, MAP_HEIGHT) * ring
            for i in range(10):
                angle = (i / 10) * math.tau + ring
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
            if not self.session.paused:
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
                if event.key == pygame.K_q:
                    self._trigger_battle_cry()
                if event.key == pygame.K_m:
                    self.audio.toggle_music()
                if event.key == pygame.K_p:
                    self.session.paused = not self.session.paused
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
            if math.hypot(unit.x - x, unit.y - y) < 18:
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
            hp = 200
        else:
            cost = (120, 100)
            building_type = "tower"
            hp = 180
        if not nation.can_afford(*cost):
            self._push_message("Not enough resources.")
            self.audio.play("warning")
            return
        if self._too_close_to_base(pos, nation.base_pos) or self._building_at_position(pos):
            self._push_message("Placement blocked.")
            self.audio.play("warning")
            return
        nation.spend(*cost)
        nation.buildings.append(
            Building(
                x=float(pos[0]),
                y=float(pos[1]),
                building_type=building_type,
                hp=hp,
                max_hp=hp,
                nation_id=nation.nation_id,
            )
        )
        self._push_message(f"{building_type.title()} constructed.")
        self.audio.play("place")
        self.session.build_mode = None

    def _train_soldier(self) -> None:
        nation = self.session.nations[self.session.selected_nation]
        if nation.supply_used() >= nation.supply_cap():
            self._push_message("Supply cap reached. Build more towers/barracks.")
            self.audio.play("warning")
            return
        if not any(building.building_type == "barracks" for building in nation.buildings):
            self._push_message("Build a barracks to train soldiers.")
            self.audio.play("warning")
            return
        if not nation.can_afford(90, 30):
            self._push_message("Not enough resources.")
            self.audio.play("warning")
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
                hp=90,
                speed=72,
                attack=18,
                range=55,
                cooldown=1.1,
            )
        )
        self.audio.play("train")

    def _train_worker(self) -> None:
        nation = self.session.nations[self.session.selected_nation]
        if nation.supply_used() >= nation.supply_cap():
            self._push_message("Supply cap reached. Build more towers/barracks.")
            self.audio.play("warning")
            return
        if not nation.can_afford(50, 15):
            self._push_message("Not enough resources.")
            self.audio.play("warning")
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
                hp=55,
                speed=55,
                attack=4,
                range=25,
                cooldown=1.4,
            )
        )
        self.audio.play("train")

    def _research_tier(self) -> None:
        nation = self.session.nations[self.session.selected_nation]
        if nation.tech_tier >= 4:
            self._push_message("Tech tree fully researched.")
            self.audio.play("warning")
            return
        costs = {
            1: (280, 180),
            2: (520, 360),
            3: (820, 520),
        }
        gold, lumber = costs.get(nation.tech_tier, (0, 0))
        if not nation.can_afford(gold, lumber):
            self._push_message("Not enough resources.")
            self.audio.play("warning")
            return
        nation.spend(gold, lumber)
        nation.tech_tier += 1
        self._push_message(f"Tech Tier {nation.tech_tier} reached.")
        self.audio.play("train")

    def _trigger_battle_cry(self) -> None:
        nation = self.session.nations[self.session.selected_nation]
        hero = next((unit for unit in nation.units if unit.unit_type == "hero"), None)
        if not hero:
            self._push_message("No hero available.")
            self.audio.play("warning")
            return
        if nation.hero_cooldown > 0:
            self._push_message("Hero ability recharging.")
            self.audio.play("warning")
            return
        nation.hero_cooldown = 18.0
        hero.buff_timer = 6.0
        for unit in nation.units:
            if unit.unit_type in {"soldier", "worker"} and self._distance((unit.x, unit.y), (hero.x, hero.y)) < 160:
                unit.buff_timer = 6.0
        self._push_message("Battle cry! Units gain speed and attack.")
        self.audio.play("buff")

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
            if nation.hero_cooldown > 0:
                nation.hero_cooldown = max(0.0, nation.hero_cooldown - dt)
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
                    hp=90,
                    speed=72,
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
                    hp=55,
                    speed=55,
                    attack=4,
                    range=25,
                    cooldown=1.4,
                )
            )
        for unit in nation.units:
            if unit.unit_type == "soldier" and unit.target is None:
                offset = random.uniform(-60, 60)
                unit.target = (
                    nation.base_pos[0] + offset,
                    nation.base_pos[1] + offset,
                )
        if nation.tech_tier < 3 and nation.can_afford(320, 220):
            nation.spend(320, 220)
            nation.tech_tier += 1
        if not has_barracks and nation.can_afford(140, 80):
            nation.spend(140, 80)
            base_x, base_y = nation.base_pos
            nation.buildings.append(
                Building(
                    x=base_x + random.uniform(-60, 60),
                    y=base_y + random.uniform(-60, 60),
                    building_type="barracks",
                    hp=200,
                    max_hp=200,
                    nation_id=nation.nation_id,
                )
            )
        if nation.can_afford(120, 100) and len(nation.buildings) < 4:
            base_x, base_y = nation.base_pos
            nation.spend(120, 100)
            nation.buildings.append(
                Building(
                    x=base_x + random.uniform(-90, 90),
                    y=base_y + random.uniform(-90, 90),
                    building_type="tower",
                    hp=180,
                    max_hp=180,
                    nation_id=nation.nation_id,
                )
            )
        if nation.hero_cooldown <= 0:
            hero = next((unit for unit in nation.units if unit.unit_type == "hero"), None)
            if hero and random.random() < 0.02:
                nation.hero_cooldown = 18.0
                hero.buff_timer = 4.5

    def _spawn_zombies(self, dt: float) -> None:
        session = self.session
        phase = session.phase()
        session.spawn_timer += dt
        spawn_interval = max(1.6, 4.4 - phase["threat_multiplier"])
        if session.spawn_timer < spawn_interval:
            return
        session.spawn_timer = 0
        count = int(2 + phase["threat_multiplier"] * 2.4)
        variants = ["shambler"]
        if phase["start"] >= 15:
            variants.append("runner")
            variants.append("spitter")
        if phase["start"] >= 30:
            variants.append("brute")
        if phase["start"] >= 45 and random.random() < 0.18:
            variants.append("boss")
            count = max(count - 2, 1)
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
            kind = random.choice(variants)
            spec = ZOMBIE_VARIANTS[kind]
            session.zombies.append(
                Zombie(
                    x=x,
                    y=y,
                    kind=kind,
                    hp=spec["hp"],
                    speed=spec["speed"],
                    attack=spec["attack"],
                    range=spec["range"],
                    cooldown=spec["cooldown"],
                )
            )
        if session.minute - session.last_spawn_sound > 0.6:
            self.audio.play("spawn")
            session.last_spawn_sound = session.minute

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
                    target.hp -= unit.current_attack
                    unit.cooldown_timer = unit.cooldown
                    unit.xp += 4
                    if unit.xp >= unit.level * 80:
                        unit.level += 1
                        unit.hp += 10
                        unit.attack += 2
                        unit.xp = 0
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
                    elif unit.unit_type == "soldier":
                        nation.soldiers = max(0, nation.soldiers - 1)
        for zombie in list(session.zombies):
            if zombie.hp <= 0:
                session.zombies.remove(zombie)
                session.zombies_slain += 1
        for nation in session.nations:
            for zombie in list(session.zombies):
                if self._distance((zombie.x, zombie.y), nation.base_pos) < 24:
                    nation.base_hp = max(0, nation.base_hp - zombie.attack * dt)
                    if nation.base_hp == 0:
                        self._push_message(f"{nation.blueprint_name} has fallen.")
                        self.audio.play("warning")

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
            target = self._closest_zombie(building.x, building.y, 150)
            if target:
                target.hp -= 12 + nation.tech_tier * 3
                building.cooldown_timer = 1.1

    def _cleanup_destroyed(self) -> None:
        for nation in self.session.nations:
            for building in list(nation.buildings):
                if building.hp <= 0 and building.building_type != "base":
                    nation.buildings.remove(building)
        for node in list(self.session.nodes):
            if node.amount <= 0:
                self.session.nodes.remove(node)

    def _check_game_over(self) -> None:
        session = self.session
        player = session.nations[0]
        if player.base_hp <= 0:
            session.game_over = True
            session.victory = False
            self.audio.play("defeat")
            return
        if session.minute >= session.objective_minutes and session.zombies_slain >= session.objective_kills:
            session.game_over = True
            session.victory = True
            self.audio.play("victory")
            return
        living = session.living_nations()
        if not living:
            session.game_over = True
            session.victory = False
            self.audio.play("defeat")

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
        self.screen.blit(self.background, (0, 0))
        pygame.draw.rect(self.screen, COLOR_PANEL, (0, MAP_HEIGHT, SCREEN_WIDTH, UI_HEIGHT))
        self._draw_map()
        self._draw_ui()
        if self.session.game_over:
            self._draw_game_over()
        if self.session.paused and not self.session.game_over:
            self._draw_paused()
        pygame.display.flip()

    def _draw_map(self) -> None:
        for node in self.session.nodes:
            color = COLOR_GOLD if node.kind == "gold" else COLOR_LUMBER
            pygame.draw.circle(self.screen, color, (int(node.x), int(node.y)), 10)
            ring_radius = max(4, int(10 * (node.amount / 1200)))
            pygame.draw.circle(self.screen, COLOR_RESOURCE, (int(node.x), int(node.y)), ring_radius, 2)
        for idx, nation in enumerate(self.session.nations):
            if nation.base_hp <= 0:
                continue
            color = NATION_COLORS[idx]
            base_x, base_y = nation.base_pos
            pygame.draw.circle(self.screen, color, (int(base_x), int(base_y)), 22)
            pygame.draw.circle(self.screen, COLOR_ACCENT, (int(base_x), int(base_y)), 28, 2)
            self._draw_health_bar((base_x - 26, base_y - 38), 52, nation.base_hp / nation.base_max_hp)
            for building in nation.buildings:
                if building.building_type == "barracks":
                    rect = pygame.Rect(0, 0, 26, 26)
                    rect.center = (building.x, building.y)
                    pygame.draw.rect(self.screen, COLOR_BARRACKS, rect)
                    self._draw_health_bar((building.x - 13, building.y - 22), 26, building.hp / building.max_hp)
                elif building.building_type == "tower":
                    pygame.draw.circle(
                        self.screen,
                        COLOR_TOWER,
                        (int(building.x), int(building.y)),
                        13,
                    )
                    self._draw_health_bar((building.x - 13, building.y - 22), 26, building.hp / building.max_hp)
            for unit in nation.units:
                if unit.unit_type == "hero":
                    radius = 10
                    pygame.draw.circle(self.screen, COLOR_HIGHLIGHT, (int(unit.x), int(unit.y)), radius + 3)
                else:
                    radius = 6 if unit.unit_type == "worker" else 8
                pygame.draw.circle(self.screen, color, (int(unit.x), int(unit.y)), radius)
                if unit is self.session.selected_unit:
                    pygame.draw.circle(
                        self.screen,
                        COLOR_SELECTION,
                        (int(unit.x), int(unit.y)),
                        radius + 5,
                        2,
                    )
                if unit.buff_timer > 0:
                    pygame.draw.circle(
                        self.screen,
                        COLOR_HIGHLIGHT,
                        (int(unit.x), int(unit.y)),
                        radius + 2,
                        1,
                    )
        for zombie in self.session.zombies:
            spec = ZOMBIE_VARIANTS.get(zombie.kind, ZOMBIE_VARIANTS["shambler"])
            pygame.draw.circle(
                self.screen,
                spec["color"],
                (int(zombie.x), int(zombie.y)),
                spec["size"],
            )

        if self.session.build_mode:
            self._draw_build_preview()

    def _draw_build_preview(self) -> None:
        pos = pygame.mouse.get_pos()
        if pos[1] >= MAP_HEIGHT:
            return
        color = COLOR_BARRACKS if self.session.build_mode == "barracks" else COLOR_TOWER
        if self.session.build_mode == "barracks":
            rect = pygame.Rect(0, 0, 26, 26)
            rect.center = pos
            pygame.draw.rect(self.screen, color, rect, 2)
        else:
            pygame.draw.circle(self.screen, color, pos, 13, 2)

    def _draw_ui(self) -> None:
        nation = self.session.nations[self.session.selected_nation]
        phase = self.session.phase()
        header = f"Nation {self.session.selected_nation + 1}: {nation.blueprint_name}"
        self._blit_text(header, 20, MAP_HEIGHT + 12, self.large_font)
        stats = (
            f"Gold {nation.resources.gold:,.0f}  Lumber {nation.resources.lumber:,.0f}  "
            f"Supply {nation.supply_used()}/{nation.supply_cap()}  "
            f"Workers {nation.workers}  Soldiers {nation.soldiers}  Tier {nation.tech_tier}"
        )
        self._blit_text(stats, 20, MAP_HEIGHT + 44, self.font)
        phase_text = f"Zombie Phase: {phase['name']} ({phase['special']})"
        self._blit_text(phase_text, 20, MAP_HEIGHT + 70, self.font)
        objective = (
            f"Objective: Survive {self.session.objective_minutes:.0f} min + "
            f"{self.session.objective_kills} kills"
        )
        self._blit_text(objective, 20, MAP_HEIGHT + 96, self.font)
        controls = (
            "Controls: 1-8 switch | LMB select/place | RMB move/harvest | "
            "S soldier | W worker | R tech | B barracks | D tower | Q battle cry | M music | P pause"
        )
        self._blit_text(controls, 20, MAP_HEIGHT + 122, self.font)
        living = len(self.session.living_nations())
        status = (
            f"Zombies: {len(self.session.zombies)} | Slain: {self.session.zombies_slain} | "
            f"Nations Standing: {living}"
        )
        self._blit_text(status, 800, MAP_HEIGHT + 44, self.font)
        hero_status = "Ready" if nation.hero_cooldown <= 0 else f"{nation.hero_cooldown:,.0f}s"
        self._blit_text(f"Battle Cry: {hero_status}", 800, MAP_HEIGHT + 70, self.font)
        if self.session.build_mode:
            self._blit_text(
                f"Build Mode: {self.session.build_mode.title()}",
                800,
                MAP_HEIGHT + 96,
                self.font,
                color=COLOR_ALERT,
            )
        self._draw_messages()

    def _draw_game_over(self) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, MAP_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 10, 12, 210))
        self.screen.blit(overlay, (0, 0))
        message = "Victory! The living endure." if self.session.victory else "Defeat. The undead prevail."
        self._blit_text(message, 420, MAP_HEIGHT / 2 - 20, self.large_font)
        self._blit_text("Press Esc to exit.", 470, MAP_HEIGHT / 2 + 10, self.font)

    def _draw_paused(self) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, MAP_HEIGHT), pygame.SRCALPHA)
        overlay.fill((12, 12, 16, 140))
        self.screen.blit(overlay, (0, 0))
        self._blit_text("Paused", 580, MAP_HEIGHT / 2 - 10, self.large_font)

    def _draw_messages(self) -> None:
        base_y = MAP_HEIGHT + 10
        for idx, message in enumerate(self.session.messages[-3:]):
            self._blit_text(message, 800, base_y + idx * 20, self.font, color=COLOR_ALERT)

    def _draw_health_bar(self, pos: tuple[float, float], width: int, ratio: float) -> None:
        ratio = max(0.0, min(1.0, ratio))
        bar_rect = pygame.Rect(int(pos[0]), int(pos[1]), width, 4)
        pygame.draw.rect(self.screen, (40, 40, 50), bar_rect)
        fill_rect = pygame.Rect(int(pos[0]), int(pos[1]), int(width * ratio), 4)
        pygame.draw.rect(self.screen, (120, 200, 120), fill_rect)

    def _blit_text(
        self,
        text: str,
        x: float,
        y: float,
        font: pygame.font.Font,
        color: tuple[int, int, int] = COLOR_TEXT,
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
                if self._distance(pos, (building.x, building.y)) < 22:
                    return True
        return False

    @staticmethod
    def _too_close_to_base(pos: tuple[int, int], base: tuple[float, float]) -> bool:
        return math.hypot(pos[0] - base[0], pos[1] - base[1]) < 40


def main() -> None:
    if os.environ.get("SDL_AUDIODRIVER") == "dummy":
        pygame.mixer.quit()
    app = GameApp()
    app.run()


if __name__ == "__main__":
    main()
