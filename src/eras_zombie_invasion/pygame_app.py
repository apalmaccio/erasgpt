from __future__ import annotations

import json
import math
import os
import random
import select
import socket
from array import array
from dataclasses import dataclass, field

import pygame

from .data import NATIONS, ZOMBIE_PHASES

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
UI_HEIGHT = 170
MAP_HEIGHT = SCREEN_HEIGHT - UI_HEIGHT
FPS = 60
MAX_PLAYERS = 4
NETWORK_PORT = 5050

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
class LobbySlot:
    slot_id: int
    nation_id: int
    status: str = "open"
    ready: bool = False
    player_name: str = "Open"
    connection_id: int | None = None


@dataclass
class LobbyState:
    slots: list[LobbySlot]
    active_slot: int = 0
    info_message: str = "Host or join to begin."
    ip_input: str = ""
    name_input: str = "Player"


class NetworkSession:
    def __init__(self) -> None:
        self.role: str | None = None
        self.server: socket.socket | None = None
        self.socket: socket.socket | None = None
        self.clients: dict[int, socket.socket] = {}
        self.recv_buffers: dict[socket.socket, str] = {}
        self.inbox: list[dict] = []
        self.next_client_id = 1

    def host(self, port: int) -> None:
        self.role = "host"
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("0.0.0.0", port))
        self.server.listen()
        self.server.setblocking(False)

    def join(self, host: str, port: int) -> None:
        self.role = "client"
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setblocking(False)
        self.socket.connect_ex((host, port))

    def close(self) -> None:
        if self.server:
            self.server.close()
        if self.socket:
            self.socket.close()
        for client in self.clients.values():
            client.close()
        self.server = None
        self.socket = None
        self.clients.clear()
        self.recv_buffers.clear()
        self.inbox.clear()
        self.role = None

    def poll(self) -> None:
        sockets: list[socket.socket] = []
        if self.server:
            sockets.append(self.server)
        if self.socket:
            sockets.append(self.socket)
        sockets.extend(self.clients.values())
        if not sockets:
            return
        readable, _, _ = select.select(sockets, [], [], 0)
        for sock in readable:
            if sock is self.server:
                self._accept_client()
            else:
                self._receive(sock)

    def _accept_client(self) -> None:
        if not self.server:
            return
        try:
            client, _ = self.server.accept()
        except BlockingIOError:
            return
        client.setblocking(False)
        client_id = self.next_client_id
        self.next_client_id += 1
        self.clients[client_id] = client
        self.recv_buffers[client] = ""
        self.inbox.append({"type": "client_joined", "client_id": client_id})

    def _receive(self, sock: socket.socket) -> None:
        try:
            data = sock.recv(4096)
        except BlockingIOError:
            return
        if not data:
            self._disconnect(sock)
            return
        buffer = self.recv_buffers.get(sock, "") + data.decode("utf-8")
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            if not line.strip():
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            message["_socket"] = sock
            self.inbox.append(message)
        self.recv_buffers[sock] = buffer

    def _disconnect(self, sock: socket.socket) -> None:
        sock.close()
        self.recv_buffers.pop(sock, None)
        if self.socket is sock:
            self.socket = None
        else:
            client_id = next((cid for cid, csock in self.clients.items() if csock is sock), None)
            if client_id is not None:
                self.clients.pop(client_id, None)
                self.inbox.append({"type": "client_left", "client_id": client_id})

    def send(self, message: dict, target: socket.socket | None = None) -> None:
        data = (json.dumps(message) + "\n").encode("utf-8")
        if target:
            try:
                target.sendall(data)
            except OSError:
                self._disconnect(target)
            return
        if self.role == "client" and self.socket:
            try:
                self.socket.sendall(data)
            except OSError:
                self._disconnect(self.socket)
            return
        if self.role == "host":
            for client in list(self.clients.values()):
                try:
                    client.sendall(data)
                except OSError:
                    self._disconnect(client)

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
    unit_id: int
    hp: float
    speed: float
    attack: float
    range: float
    cooldown: float
    target: tuple[float, float] | None = None
    harvest_node_id: int | None = None
    order_type: str | None = None
    order_target_id: int | None = None
    order_pos: tuple[float, float] | None = None
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
    zombie_id: int
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
    building_id: int
    cooldown_timer: float = 0.0


@dataclass
class GameSession:
    nations: list[NationState]
    zombies: list[Zombie]
    nodes: list[ResourceNode]
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
    next_unit_id: int = 1
    next_building_id: int = 1
    next_zombie_id: int = 1
    network_timer: float = 0.0

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
        self.small_font = pygame.font.SysFont("consolas", 15)
        self.mode = "lobby"
        self.network = NetworkSession()
        self.lobby = self._create_lobby()
        self.session = self._create_session()
        self.running = True
        self.audio = AudioManager()
        self.audio.play_music()
        self.background = self._generate_background()
        self.unit_sprites = self._build_unit_sprites()
        self.selected_units: list[int] = []
        self.selected_building: Building | None = None
        self.drag_start: tuple[int, int] | None = None
        self.drag_rect: pygame.Rect | None = None
        self.dragging = False
        self.local_slot_id = 0
        self.local_nation_id = 0

    def _generate_background(self) -> pygame.Surface:
        surface = pygame.Surface((SCREEN_WIDTH, MAP_HEIGHT))
        surface.fill(COLOR_WATER)
        land_color = (40, 70, 55)
        shore_color = (55, 90, 70)
        europe_shape = [
            (220, 120),
            (290, 80),
            (370, 70),
            (450, 80),
            (520, 120),
            (560, 170),
            (620, 190),
            (690, 210),
            (760, 200),
            (820, 230),
            (880, 240),
            (940, 270),
            (960, 320),
            (920, 360),
            (860, 380),
            (820, 400),
            (780, 420),
            (730, 450),
            (650, 470),
            (560, 470),
            (490, 450),
            (450, 420),
            (420, 380),
            (380, 340),
            (340, 310),
            (310, 280),
            (280, 240),
            (250, 200),
        ]
        iberia = [(260, 320), (290, 300), (330, 310), (360, 340), (340, 380), (300, 390), (270, 360)]
        italy = [(470, 320), (500, 330), (520, 360), (510, 390), (480, 380), (460, 350)]
        scandinavia = [(470, 60), (520, 40), (560, 60), (590, 110), (560, 130), (520, 120), (490, 90)]
        uk = [(260, 180), (270, 160), (290, 170), (300, 190), (290, 210), (270, 210)]
        greece = [(610, 360), (630, 350), (650, 360), (660, 380), (640, 400), (620, 390)]
        pygame.draw.polygon(surface, land_color, europe_shape)
        pygame.draw.polygon(surface, land_color, iberia)
        pygame.draw.polygon(surface, land_color, italy)
        pygame.draw.polygon(surface, land_color, scandinavia)
        pygame.draw.polygon(surface, land_color, uk)
        pygame.draw.polygon(surface, land_color, greece)
        pygame.draw.lines(surface, shore_color, True, europe_shape, 3)
        for landmass in (iberia, italy, scandinavia, uk, greece):
            pygame.draw.lines(surface, shore_color, True, landmass, 2)
        for x in range(0, SCREEN_WIDTH, 80):
            pygame.draw.line(surface, COLOR_GRID, (x, 0), (x, MAP_HEIGHT))
        for y in range(0, MAP_HEIGHT, 80):
            pygame.draw.line(surface, COLOR_GRID, (0, y), (SCREEN_WIDTH, y))
        self._draw_map_labels(surface)
        return surface

    def _draw_map_labels(self, surface: pygame.Surface) -> None:
        labels = [
            ("United Kingdom", (250, 150)),
            ("France", (350, 260)),
            ("Spain", (300, 340)),
            ("Germany", (450, 220)),
            ("Italy", (470, 330)),
            ("Poland", (560, 230)),
            ("Sweden", (500, 90)),
            ("Greece", (620, 360)),
        ]
        for name, pos in labels:
            text = self.small_font.render(name, True, (200, 220, 200))
            surface.blit(text, pos)

    def _create_lobby(self) -> LobbyState:
        slots: list[LobbySlot] = []
        for slot_id in range(MAX_PLAYERS):
            if slot_id == 0:
                slots.append(
                    LobbySlot(
                        slot_id=slot_id,
                        nation_id=0,
                        status="local",
                        ready=False,
                        player_name="Host",
                    )
                )
            else:
                slots.append(LobbySlot(slot_id=slot_id, nation_id=slot_id % len(NATIONS)))
        return LobbyState(slots=slots)

    def _build_unit_sprites(self) -> dict[tuple[int, str], pygame.Surface]:
        sprites: dict[tuple[int, str], pygame.Surface] = {}
        for nation_id, base_color in enumerate(NATION_COLORS):
            for unit_type in ("worker", "soldier", "hero"):
                size = 20 if unit_type == "hero" else 14
                surface = pygame.Surface((size, size), pygame.SRCALPHA)
                highlight = tuple(min(255, c + 40) for c in base_color)
                shadow = tuple(max(0, c - 40) for c in base_color)
                if unit_type == "worker":
                    pygame.draw.circle(surface, base_color, (size // 2, size // 2), size // 2)
                    pygame.draw.line(
                        surface,
                        highlight,
                        (size // 2, size // 2),
                        (size - 2, 2),
                        2,
                    )
                elif unit_type == "soldier":
                    pygame.draw.rect(surface, base_color, pygame.Rect(2, 2, size - 4, size - 4), border_radius=3)
                    pygame.draw.line(surface, shadow, (2, size - 3), (size - 3, 2), 2)
                else:
                    pygame.draw.circle(surface, highlight, (size // 2, size // 2), size // 2)
                    pygame.draw.circle(surface, base_color, (size // 2, size // 2), size // 2 - 3)
                    pygame.draw.circle(surface, shadow, (size // 2, size // 2), 3)
                sprites[(nation_id, unit_type)] = surface
        return sprites

    def _create_session(self) -> GameSession:
        nations: list[NationState] = []
        nodes: list[ResourceNode] = []
        base_positions = {
            "United Kingdom": (270, 190),
            "France": (360, 260),
            "Spain": (320, 350),
            "Germany": (460, 220),
            "Italy": (480, 330),
            "Poland": (560, 230),
            "Sweden": (520, 110),
            "Greece": (620, 370),
        }
        session = GameSession(nations=[], zombies=[], nodes=[])
        for idx, blueprint in enumerate(NATIONS):
            base_x, base_y = base_positions.get(blueprint.name, (400 + idx * 40, 240 + idx * 20))
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
                    building_id=session.next_building_id,
                )
            )
            session.next_building_id += 1
            for i in range(nation.soldiers):
                offset = 14 * i
                nation.units.append(
                    Unit(
                        x=base_x + offset,
                        y=base_y + 25,
                        unit_type="soldier",
                        nation_id=idx,
                        unit_id=session.next_unit_id,
                        hp=90,
                        speed=72,
                        attack=18,
                        range=55,
                        cooldown=1.1,
                    )
                )
                session.next_unit_id += 1
            for i in range(nation.workers):
                offset = -12 * i
                nation.units.append(
                    Unit(
                        x=base_x + offset,
                        y=base_y - 25,
                        unit_type="worker",
                        nation_id=idx,
                        unit_id=session.next_unit_id,
                        hp=55,
                        speed=55,
                        attack=4,
                        range=25,
                        cooldown=1.4,
                    )
                )
                session.next_unit_id += 1
            if idx == 0:
                nation.units.append(
                    Unit(
                        x=base_x + 20,
                        y=base_y,
                        unit_type="hero",
                        nation_id=idx,
                        unit_id=session.next_unit_id,
                        hp=220,
                        speed=82,
                        attack=26,
                        range=65,
                        cooldown=0.9,
                    )
                )
                session.next_unit_id += 1
            nations.append(nation)
        node_id = 0
        for base in base_positions.values():
            for offset, kind in ((-40, "gold"), (40, "lumber")):
                nodes.append(
                    ResourceNode(
                        node_id=node_id,
                        x=base[0] + offset,
                        y=base[1] + 55,
                        kind=kind,
                    )
                )
                node_id += 1
        session.nations = nations
        session.nodes = nodes
        return session

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self.network.poll()
            self._handle_network_messages()
            self._handle_events()
            if self.mode == "game":
                if not self.session.paused and not self._is_network_client():
                    self._update(dt)
                if self._is_network_host():
                    self._broadcast_state(dt)
            self._render()
        pygame.quit()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if self.mode == "lobby":
                self._handle_lobby_event(event)
            else:
                self._handle_game_event(event)

    def _handle_lobby_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_h:
                self._start_hosting()
                return
            if event.key == pygame.K_j:
                self._start_joining()
                return
            if event.key == pygame.K_RETURN:
                if self._is_network_client() and self.network.socket:
                    self.network.send(
                        {
                            "type": "ready",
                            "ready": self._toggle_local_ready(),
                        }
                    )
            if event.key == pygame.K_BACKSPACE:
                if self.lobby.ip_input:
                    self.lobby.ip_input = self.lobby.ip_input[:-1]
            if event.unicode and event.key not in (pygame.K_RETURN, pygame.K_BACKSPACE):
                if event.unicode.isprintable():
                    if event.unicode in "0123456789.:" and len(self.lobby.ip_input) < 24:
                        self.lobby.ip_input += event.unicode
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_lobby_click(event.pos)

    def _handle_game_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if not self._is_network_client():
                if pygame.K_1 <= event.key <= pygame.K_8:
                    self.session.selected_nation = event.key - pygame.K_1
                    self.session.build_mode = None
            if event.key == pygame.K_s:
                self._queue_command({"action": "train_soldier"})
            if event.key == pygame.K_w:
                self._queue_command({"action": "train_worker"})
            if event.key == pygame.K_r:
                self._queue_command({"action": "research"})
            if event.key == pygame.K_b:
                self.session.build_mode = "barracks"
            if event.key == pygame.K_d:
                self.session.build_mode = "tower"
            if event.key == pygame.K_q:
                self._queue_command({"action": "battle_cry"})
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
                if event.pos[1] < MAP_HEIGHT:
                    if self.session.build_mode:
                        self._queue_command({"action": "place_building", "pos": event.pos})
                    else:
                        self.drag_start = event.pos
                        self.dragging = True
                        self.drag_rect = None
            if event.button == 3:
                if event.pos[1] < MAP_HEIGHT:
                    self._queue_command({"action": "order", "pos": event.pos})
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging and self.drag_start:
                end_pos = event.pos
                self.dragging = False
                if self.drag_rect and self.drag_rect.width > 6 and self.drag_rect.height > 6:
                    self._select_units_in_rect(self.drag_rect)
                else:
                    self._select_units_at_pos(end_pos)
                self.drag_rect = None
                self.drag_start = None
        if event.type == pygame.MOUSEMOTION and self.dragging and self.drag_start:
            current = event.pos
            x1, y1 = self.drag_start
            x2, y2 = current
            rect = pygame.Rect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
            self.drag_rect = rect

    def _is_network_host(self) -> bool:
        return self.network.role == "host"

    def _is_network_client(self) -> bool:
        return self.network.role == "client"

    def _start_hosting(self) -> None:
        if self.network.role:
            return
        self.network.host(NETWORK_PORT)
        self.lobby.info_message = f"Hosting on port {NETWORK_PORT}. Waiting for players..."

    def _start_joining(self) -> None:
        if self.network.role:
            return
        host = self.lobby.ip_input.strip() or "127.0.0.1"
        self.network.join(host, NETWORK_PORT)
        self.network.send({"type": "join", "name": self.lobby.name_input or "Player"})
        self.lobby.info_message = f"Connecting to {host}:{NETWORK_PORT}..."

    def _handle_lobby_click(self, pos: tuple[int, int]) -> None:
        slot_height = 80
        start_y = 120
        for slot in self.lobby.slots:
            rect = pygame.Rect(120, start_y + slot.slot_id * slot_height, 860, 70)
            if rect.collidepoint(pos):
                self.lobby.active_slot = slot.slot_id
                left_arrow = pygame.Rect(rect.right - 210, rect.y + 20, 24, 30)
                right_arrow = pygame.Rect(rect.right - 120, rect.y + 20, 24, 30)
                ready_rect = pygame.Rect(rect.right - 80, rect.y + 18, 70, 34)
                status_rect = pygame.Rect(rect.x + 10, rect.y + 18, 90, 34)
                if status_rect.collidepoint(pos) and self._is_network_host():
                    self._cycle_slot_status(slot)
                    return
                if left_arrow.collidepoint(pos) and self._can_edit_slot(slot):
                    self._change_slot_nation(slot, -1)
                    return
                if right_arrow.collidepoint(pos) and self._can_edit_slot(slot):
                    self._change_slot_nation(slot, 1)
                    return
                if ready_rect.collidepoint(pos) and slot.status in {"local", "remote"}:
                    if slot.status == "local":
                        self._toggle_local_ready()
                return
        start_rect = pygame.Rect(520, 520, 220, 48)
        if start_rect.collidepoint(pos):
            if self._is_network_host() and self._all_ready():
                self._start_game()
            elif not self.network.role:
                self._start_game()

    def _cycle_slot_status(self, slot: LobbySlot) -> None:
        if slot.status == "local":
            return
        order = ["open", "ai", "closed"]
        next_status = order[(order.index(slot.status) + 1) % len(order)]
        slot.status = next_status
        slot.player_name = "AI" if slot.status == "ai" else "Open" if slot.status == "open" else "Closed"
        slot.ready = slot.status == "ai"
        self._broadcast_lobby_state()

    def _toggle_local_ready(self) -> bool:
        slot = self._local_lobby_slot()
        if not slot:
            return False
        slot.ready = not slot.ready
        self._broadcast_lobby_state()
        return slot.ready

    def _local_lobby_slot(self) -> LobbySlot | None:
        if 0 <= self.local_slot_id < len(self.lobby.slots):
            return self.lobby.slots[self.local_slot_id]
        return None

    def _can_edit_slot(self, slot: LobbySlot) -> bool:
        if self._is_network_host():
            return slot.status in {"local", "ai", "open", "remote"}
        if self._is_network_client():
            return slot.status == "local"
        return True

    def _change_slot_nation(self, slot: LobbySlot, direction: int) -> None:
        slot.nation_id = (slot.nation_id + direction) % len(NATIONS)
        if self._is_network_client():
            self.network.send({"type": "nation", "nation_id": slot.nation_id})
        else:
            self._broadcast_lobby_state()

    def _all_ready(self) -> bool:
        for slot in self.lobby.slots:
            if slot.status in {"local", "remote"} and not slot.ready:
                return False
        return any(slot.status in {"local", "remote", "ai"} for slot in self.lobby.slots)

    def _queue_command(self, payload: dict) -> None:
        if self.mode != "game":
            return
        if self._is_network_client():
            payload.update({"type": "command"})
            if payload.get("action") == "order":
                payload["unit_ids"] = list(self.selected_units)
            if payload.get("action") == "place_building":
                payload["building_type"] = self.session.build_mode
            self.network.send(payload)
        else:
            self._apply_command(payload, self.session.selected_nation)

    def _apply_command(self, payload: dict, nation_id: int) -> None:
        action = payload.get("action")
        if action == "train_soldier":
            self._train_soldier(nation_id)
        elif action == "train_worker":
            self._train_worker(nation_id)
        elif action == "research":
            self._research_tier(nation_id)
        elif action == "battle_cry":
            self._trigger_battle_cry(nation_id)
        elif action == "place_building":
            pos = payload.get("pos")
            building_type = payload.get("building_type")
            if pos and building_type:
                self._place_building(pos, nation_id, building_type)
        elif action == "order":
            unit_ids = payload.get("unit_ids", list(self.selected_units))
            pos = payload.get("pos")
            if pos:
                self._issue_order(nation_id, unit_ids, pos)

    def _handle_network_messages(self) -> None:
        for message in list(self.network.inbox):
            self.network.inbox.remove(message)
            if self._is_network_host():
                self._handle_host_message(message)
            elif self._is_network_client():
                self._handle_client_message(message)

    def _handle_host_message(self, message: dict) -> None:
        msg_type = message.get("type")
        if msg_type == "client_joined":
            self._assign_client_to_slot(message["client_id"])
            return
        if msg_type == "client_left":
            self._remove_client_from_slot(message["client_id"])
            return
        if msg_type == "join":
            slot = self._slot_for_socket(message.get("_socket"))
            if slot:
                slot.player_name = message.get("name", "Player")
                slot.ready = False
                self._broadcast_lobby_state()
            return
        if msg_type == "ready":
            slot = self._slot_for_socket(message.get("_socket"))
            if slot:
                slot.ready = bool(message.get("ready"))
                self._broadcast_lobby_state()
            return
        if msg_type == "nation":
            slot = self._slot_for_socket(message.get("_socket"))
            if slot:
                slot.nation_id = int(message.get("nation_id", slot.nation_id))
                self._broadcast_lobby_state()
            return
        if msg_type == "command":
            slot = self._slot_for_socket(message.get("_socket"))
            if slot and self.mode == "game":
                self._apply_command(message, slot.nation_id)

    def _handle_client_message(self, message: dict) -> None:
        msg_type = message.get("type")
        if msg_type == "assign":
            self.local_slot_id = int(message.get("slot_id", 0))
        if msg_type == "lobby_state":
            self._apply_lobby_state(message.get("slots", []))
        if msg_type == "start_game":
            self._start_game_from_network(message)
        if msg_type == "state":
            self._apply_network_state(message.get("state", {}))

    def _assign_client_to_slot(self, client_id: int) -> None:
        for slot in self.lobby.slots:
            if slot.status == "open":
                slot.status = "remote"
                slot.connection_id = client_id
                slot.player_name = f"Player {client_id}"
                slot.ready = False
                self.network.send(
                    {"type": "assign", "slot_id": slot.slot_id},
                    self.network.clients.get(client_id),
                )
                self._broadcast_lobby_state()
                return
        self.network.send({"type": "message", "text": "Lobby full."}, self.network.clients.get(client_id))

    def _remove_client_from_slot(self, client_id: int) -> None:
        for slot in self.lobby.slots:
            if slot.connection_id == client_id:
                slot.status = "open"
                slot.connection_id = None
                slot.player_name = "Open"
                slot.ready = False
                self._broadcast_lobby_state()
                return

    def _slot_for_socket(self, sock: socket.socket | None) -> LobbySlot | None:
        if sock is None:
            return None
        client_id = next((cid for cid, csock in self.network.clients.items() if csock is sock), None)
        if client_id is None:
            return None
        return next((slot for slot in self.lobby.slots if slot.connection_id == client_id), None)

    def _broadcast_lobby_state(self) -> None:
        if not self._is_network_host():
            return
        payload = {
            "type": "lobby_state",
            "slots": [
                {
                    "slot_id": slot.slot_id,
                    "nation_id": slot.nation_id,
                    "status": slot.status,
                    "ready": slot.ready,
                    "player_name": slot.player_name,
                }
                for slot in self.lobby.slots
            ],
        }
        self.network.send(payload)

    def _apply_lobby_state(self, slots: list[dict]) -> None:
        for slot_info in slots:
            slot = self.lobby.slots[slot_info["slot_id"]]
            slot.nation_id = slot_info["nation_id"]
            slot.status = slot_info["status"]
            slot.ready = slot_info["ready"]
            slot.player_name = slot_info["player_name"]
        if self._is_network_client():
            for slot in self.lobby.slots:
                if slot.slot_id == self.local_slot_id:
                    slot.status = "local"

    def _start_game(self) -> None:
        self.session = self._create_session_from_lobby()
        self.session.selected_nation = self.local_nation_id
        self.mode = "game"
        self.selected_units = []
        self.selected_building = None
        if self._is_network_host():
            self._broadcast_lobby_state()
            self.network.send(
                {
                    "type": "start_game",
                    "slots": [
                        {
                            "slot_id": slot.slot_id,
                            "nation_id": slot.nation_id,
                            "status": slot.status,
                        }
                        for slot in self.lobby.slots
                    ],
                    "state": self._serialize_session(self.session),
                }
            )

    def _start_game_from_network(self, message: dict) -> None:
        self.mode = "game"
        self.selected_units = []
        self.selected_building = None
        if message.get("slots"):
            self._apply_lobby_state(message.get("slots", []))
        self._apply_network_state(message.get("state", {}))
        if 0 <= self.local_slot_id < len(self.lobby.slots):
            self.local_nation_id = self.lobby.slots[self.local_slot_id].nation_id
            self.session.selected_nation = self.local_nation_id

    def _broadcast_state(self, dt: float) -> None:
        if not self._is_network_host() or self.mode != "game":
            return
        self.session.network_timer += dt
        if self.session.network_timer < 0.2:
            return
        self.session.network_timer = 0.0
        self.network.send({"type": "state", "state": self._serialize_session(self.session)})

    def _create_session_from_lobby(self) -> GameSession:
        session = self._create_session()
        active_nations = {
            slot.nation_id
            for slot in self.lobby.slots
            if slot.status in {"local", "remote", "ai"}
        }
        for slot in self.lobby.slots:
            if slot.status == "local":
                self.local_nation_id = slot.nation_id
            if slot.status in {"local", "remote"}:
                session.nations[slot.nation_id].ai_controlled = False
        for nation_id, nation in enumerate(session.nations):
            if nation_id not in active_nations:
                nation.base_hp = 0
                nation.units.clear()
                nation.buildings.clear()
        return session

    def _serialize_session(self, session: GameSession) -> dict:
        return {
            "minute": session.minute,
            "zombies_slain": session.zombies_slain,
            "objective_minutes": session.objective_minutes,
            "objective_kills": session.objective_kills,
            "game_over": session.game_over,
            "victory": session.victory,
            "nations": [
                {
                    "nation_id": nation.nation_id,
                    "blueprint_name": nation.blueprint_name,
                    "base_pos": nation.base_pos,
                    "base_hp": nation.base_hp,
                    "base_max_hp": nation.base_max_hp,
                    "resources": {
                        "gold": nation.resources.gold,
                        "lumber": nation.resources.lumber,
                        "food": nation.resources.food,
                        "arcana": nation.resources.arcana,
                    },
                    "workers": nation.workers,
                    "soldiers": nation.soldiers,
                    "tech_tier": nation.tech_tier,
                    "ai_controlled": nation.ai_controlled,
                    "hero_cooldown": nation.hero_cooldown,
                    "units": [
                        {
                            "unit_id": unit.unit_id,
                            "x": unit.x,
                            "y": unit.y,
                            "unit_type": unit.unit_type,
                            "hp": unit.hp,
                            "speed": unit.speed,
                            "attack": unit.attack,
                            "range": unit.range,
                            "cooldown": unit.cooldown,
                            "cooldown_timer": unit.cooldown_timer,
                            "buff_timer": unit.buff_timer,
                            "level": unit.level,
                            "xp": unit.xp,
                        }
                        for unit in nation.units
                    ],
                    "buildings": [
                        {
                            "building_id": building.building_id,
                            "x": building.x,
                            "y": building.y,
                            "building_type": building.building_type,
                            "hp": building.hp,
                            "max_hp": building.max_hp,
                            "cooldown_timer": building.cooldown_timer,
                        }
                        for building in nation.buildings
                    ],
                }
                for nation in session.nations
            ],
            "nodes": [
                {
                    "node_id": node.node_id,
                    "x": node.x,
                    "y": node.y,
                    "kind": node.kind,
                    "amount": node.amount,
                }
                for node in session.nodes
            ],
            "zombies": [
                {
                    "zombie_id": zombie.zombie_id,
                    "x": zombie.x,
                    "y": zombie.y,
                    "kind": zombie.kind,
                    "hp": zombie.hp,
                    "speed": zombie.speed,
                    "attack": zombie.attack,
                    "range": zombie.range,
                    "cooldown": zombie.cooldown,
                    "cooldown_timer": zombie.cooldown_timer,
                }
                for zombie in session.zombies
            ],
        }

    def _apply_network_state(self, state: dict) -> None:
        session = self.session
        session.minute = state.get("minute", session.minute)
        session.zombies_slain = state.get("zombies_slain", session.zombies_slain)
        session.objective_minutes = state.get("objective_minutes", session.objective_minutes)
        session.objective_kills = state.get("objective_kills", session.objective_kills)
        session.game_over = state.get("game_over", session.game_over)
        session.victory = state.get("victory", session.victory)
        session.nodes = [
            ResourceNode(
                node_id=node["node_id"],
                x=node["x"],
                y=node["y"],
                kind=node["kind"],
                amount=node["amount"],
            )
            for node in state.get("nodes", [])
        ]
        session.zombies = [
            Zombie(
                x=zombie["x"],
                y=zombie["y"],
                zombie_id=zombie["zombie_id"],
                kind=zombie["kind"],
                hp=zombie["hp"],
                speed=zombie["speed"],
                attack=zombie["attack"],
                range=zombie["range"],
                cooldown=zombie["cooldown"],
                cooldown_timer=zombie["cooldown_timer"],
            )
            for zombie in state.get("zombies", [])
        ]
        session.nations = []
        for nation_info in state.get("nations", []):
            nation = NationState(
                blueprint_name=nation_info["blueprint_name"],
                nation_id=nation_info["nation_id"],
                base_pos=tuple(nation_info["base_pos"]),
                ai_controlled=nation_info.get("ai_controlled", True),
                base_hp=nation_info["base_hp"],
                base_max_hp=nation_info["base_max_hp"],
                workers=nation_info["workers"],
                soldiers=nation_info["soldiers"],
                tech_tier=nation_info["tech_tier"],
                hero_cooldown=nation_info.get("hero_cooldown", 0.0),
            )
            nation.resources = Resources(
                gold=nation_info["resources"]["gold"],
                lumber=nation_info["resources"]["lumber"],
                food=nation_info["resources"]["food"],
                arcana=nation_info["resources"]["arcana"],
            )
            nation.units = [
                Unit(
                    x=unit["x"],
                    y=unit["y"],
                    unit_type=unit["unit_type"],
                    nation_id=nation.nation_id,
                    unit_id=unit["unit_id"],
                    hp=unit["hp"],
                    speed=unit["speed"],
                    attack=unit["attack"],
                    range=unit["range"],
                    cooldown=unit["cooldown"],
                    cooldown_timer=unit["cooldown_timer"],
                    buff_timer=unit["buff_timer"],
                    level=unit["level"],
                    xp=unit["xp"],
                )
                for unit in nation_info["units"]
            ]
            nation.buildings = [
                Building(
                    x=building["x"],
                    y=building["y"],
                    building_type=building["building_type"],
                    hp=building["hp"],
                    nation_id=nation.nation_id,
                    max_hp=building["max_hp"],
                    building_id=building["building_id"],
                    cooldown_timer=building["cooldown_timer"],
                )
                for building in nation_info["buildings"]
            ]
            session.nations.append(nation)
        valid_ids = {unit.unit_id for nation in session.nations for unit in nation.units}
        self.selected_units = [unit_id for unit_id in self.selected_units if unit_id in valid_ids]

    def _select_units_at_pos(self, pos: tuple[int, int]) -> None:
        x, y = pos
        self.selected_building = None
        self.selected_units = []
        for unit in self._units_for_nation(self.session.selected_nation):
            if math.hypot(unit.x - x, unit.y - y) < 18:
                self.selected_units = [unit.unit_id]
                return
        for building in self.session.nations[self.session.selected_nation].buildings:
            if math.hypot(building.x - x, building.y - y) < 20:
                self.selected_building = building
                return

    def _select_units_in_rect(self, rect: pygame.Rect) -> None:
        self.selected_building = None
        self.selected_units = []
        for unit in self._units_for_nation(self.session.selected_nation):
            if rect.collidepoint(unit.x, unit.y):
                self.selected_units.append(unit.unit_id)

    def _issue_order(self, nation_id: int, unit_ids: list[int], pos: tuple[int, int]) -> None:
        if not unit_ids:
            return
        x, y = pos
        zombie = self._zombie_at_position(pos)
        node = self._node_at_position(pos)
        for unit in self._units_for_nation(nation_id):
            if unit.unit_id not in unit_ids:
                continue
            if zombie:
                unit.order_type = "attack"
                unit.order_target_id = zombie.zombie_id
                unit.order_pos = (zombie.x, zombie.y)
                unit.target = (zombie.x, zombie.y)
                unit.harvest_node_id = None
            elif node and unit.unit_type == "worker":
                unit.order_type = "harvest"
                unit.order_target_id = node.node_id
                unit.order_pos = (node.x, node.y)
                unit.harvest_node_id = node.node_id
                unit.target = (node.x, node.y)
            else:
                unit.order_type = "move"
                unit.order_target_id = None
                unit.order_pos = (float(x), float(y))
                unit.harvest_node_id = None
                unit.target = (float(x), float(y))

    def _place_building(self, pos: tuple[int, int], nation_id: int, building_type: str | None) -> None:
        nation = self.session.nations[nation_id]
        if nation.base_hp <= 0:
            return
        if building_type == "barracks":
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
                building_id=self.session.next_building_id,
            )
        )
        self.session.next_building_id += 1
        self._push_message(f"{building_type.title()} constructed.")
        self.audio.play("place")
        self.session.build_mode = None

    def _train_soldier(self, nation_id: int) -> None:
        nation = self.session.nations[nation_id]
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
                unit_id=self.session.next_unit_id,
                hp=90,
                speed=72,
                attack=18,
                range=55,
                cooldown=1.1,
            )
        )
        self.session.next_unit_id += 1
        self.audio.play("train")

    def _train_worker(self, nation_id: int) -> None:
        nation = self.session.nations[nation_id]
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
                unit_id=self.session.next_unit_id,
                hp=55,
                speed=55,
                attack=4,
                range=25,
                cooldown=1.4,
            )
        )
        self.session.next_unit_id += 1
        self.audio.play("train")

    def _research_tier(self, nation_id: int) -> None:
        nation = self.session.nations[nation_id]
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

    def _trigger_battle_cry(self, nation_id: int) -> None:
        nation = self.session.nations[nation_id]
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
                if unit.order_type == "attack":
                    target = next((z for z in session.zombies if z.zombie_id == unit.order_target_id), None)
                    if target:
                        unit.target = (target.x, target.y)
                    else:
                        unit.order_type = None
                        unit.order_target_id = None
                        unit.order_pos = None
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
                    unit_id=self.session.next_unit_id,
                    hp=90,
                    speed=72,
                    attack=18,
                    range=55,
                    cooldown=1.1,
                )
            )
            self.session.next_unit_id += 1
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
                    unit_id=self.session.next_unit_id,
                    hp=55,
                    speed=55,
                    attack=4,
                    range=25,
                    cooldown=1.4,
                )
            )
            self.session.next_unit_id += 1
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
                    building_id=self.session.next_building_id,
                )
            )
            self.session.next_building_id += 1
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
                    building_id=self.session.next_building_id,
                )
            )
            self.session.next_building_id += 1
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
                    zombie_id=session.next_zombie_id,
                    kind=kind,
                    hp=spec["hp"],
                    speed=spec["speed"],
                    attack=spec["attack"],
                    range=spec["range"],
                    cooldown=spec["cooldown"],
                )
            )
            session.next_zombie_id += 1
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
                target = None
                if unit.order_type == "attack" and unit.order_target_id is not None:
                    target = next((z for z in session.zombies if z.zombie_id == unit.order_target_id), None)
                    if target and self._distance((unit.x, unit.y), (target.x, target.y)) > unit.range:
                        target = None
                if not target:
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
                    if unit.unit_id in self.selected_units:
                        self.selected_units.remove(unit.unit_id)
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
        if self.mode == "lobby":
            self._draw_lobby()
        else:
            self.screen.blit(self.background, (0, 0))
            pygame.draw.rect(self.screen, COLOR_PANEL, (0, MAP_HEIGHT, SCREEN_WIDTH, UI_HEIGHT))
            self._draw_map()
            self._draw_ui()
            if self.drag_rect:
                pygame.draw.rect(self.screen, COLOR_SELECTION, self.drag_rect, 2)
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
                if building is self.selected_building:
                    pygame.draw.circle(
                        self.screen,
                        COLOR_SELECTION,
                        (int(building.x), int(building.y)),
                        18,
                        2,
                    )
            for unit in nation.units:
                sprite = self.unit_sprites.get((unit.nation_id, unit.unit_type))
                if sprite:
                    rect = sprite.get_rect(center=(int(unit.x), int(unit.y)))
                    self.screen.blit(sprite, rect)
                    radius = rect.width // 2
                else:
                    radius = 6 if unit.unit_type == "worker" else 8
                    pygame.draw.circle(self.screen, color, (int(unit.x), int(unit.y)), radius)
                if unit.unit_id in self.selected_units:
                    pygame.draw.circle(
                        self.screen,
                        COLOR_SELECTION,
                        (int(unit.x), int(unit.y)),
                        radius + 6,
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

    def _draw_lobby(self) -> None:
        self.screen.fill(COLOR_BG)
        title = "Eras Zombie Invasion - Lobby"
        self._blit_text(title, 420, 30, self.large_font)
        instructions = "H: Host | J: Join (type IP) | Click slot status/nation | Ready with button"
        self._blit_text(instructions, 260, 60, self.font)
        if self.lobby.info_message:
            self._blit_text(self.lobby.info_message, 320, 90, self.font, color=COLOR_HIGHLIGHT)
        self._blit_text(f"IP: {self.lobby.ip_input or '127.0.0.1'}", 120, 560, self.font)

        slot_height = 80
        start_y = 120
        for slot in self.lobby.slots:
            rect = pygame.Rect(120, start_y + slot.slot_id * slot_height, 860, 70)
            pygame.draw.rect(self.screen, COLOR_PANEL, rect, border_radius=6)
            if slot.slot_id == self.local_slot_id:
                pygame.draw.rect(self.screen, COLOR_SELECTION, rect, 2, border_radius=6)
            status_rect = pygame.Rect(rect.x + 10, rect.y + 18, 90, 34)
            pygame.draw.rect(self.screen, COLOR_ACCENT, status_rect, border_radius=4)
            self._blit_text(slot.status.title(), status_rect.x + 8, status_rect.y + 8, self.small_font)
            self._blit_text(slot.player_name, rect.x + 120, rect.y + 10, self.font)
            nation_name = NATIONS[slot.nation_id].name
            self._blit_text(nation_name, rect.x + 120, rect.y + 38, self.small_font)
            left_arrow = pygame.Rect(rect.right - 210, rect.y + 20, 24, 30)
            right_arrow = pygame.Rect(rect.right - 120, rect.y + 20, 24, 30)
            pygame.draw.rect(self.screen, COLOR_GRID, left_arrow, border_radius=2)
            pygame.draw.rect(self.screen, COLOR_GRID, right_arrow, border_radius=2)
            self._blit_text("<", left_arrow.x + 7, left_arrow.y + 5, self.font)
            self._blit_text(">", right_arrow.x + 7, right_arrow.y + 5, self.font)
            ready_rect = pygame.Rect(rect.right - 80, rect.y + 18, 70, 34)
            ready_color = (90, 170, 110) if slot.ready else COLOR_ALERT
            pygame.draw.rect(self.screen, ready_color, ready_rect, border_radius=4)
            self._blit_text("Ready" if slot.ready else "Wait", ready_rect.x + 8, ready_rect.y + 8, self.small_font)

        start_rect = pygame.Rect(520, 520, 220, 48)
        pygame.draw.rect(self.screen, COLOR_HIGHLIGHT, start_rect, border_radius=6)
        self._blit_text("Start Game", start_rect.x + 45, start_rect.y + 12, self.font)
        if not self._all_ready():
            self._blit_text("Waiting for all players ready...", 440, 580, self.font, color=COLOR_ALERT)

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
            "Controls: LMB select | LMB drag multi-select | RMB move/attack/harvest | "
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
        if self.selected_units:
            self._blit_text(
                f"Selected Units: {len(self.selected_units)}",
                800,
                MAP_HEIGHT + 122,
                self.font,
                color=COLOR_HIGHLIGHT,
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

    def _zombie_at_position(self, pos: tuple[int, int]) -> Zombie | None:
        for zombie in self.session.zombies:
            if self._distance(pos, (zombie.x, zombie.y)) < 18:
                return zombie
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
