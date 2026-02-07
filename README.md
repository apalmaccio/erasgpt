# Eras Zombie Invasion

Eras Zombie Invasion is a standalone multiplayer real-time strategy game inspired by the Warcraft III custom map of the same name. The game features eight playable nations competing against one another while holding off an ever-escalating AI-controlled zombie threat.

## Highlights
- **Multiplayer RTS** for up to 8 players.
- **Eight unique nations** with distinct economic bonuses and tech trees.
- **AI zombie invasion** that escalates in phases and responds to player actions.
- **Full economy loop** with resource harvesting, expansion, and logistics.
- **Research-driven progression** with branching tech paths.

## Repository Contents
- `docs/game_design.md` — full game design document (GDD).
- `src/eras_zombie_invasion/` — Python simulation prototype for the RTS loop.

## Quick Start (Playable Prototype)
The playable prototype is built with pygame. Install dependencies and launch:

```bash
pip install -e .
eras-zombie-invasion
```

### One-Click Launchers (Downloaded or Cloned Repo)
After installing Python 3.10+ and running `pip install -e .`, you can double-click the
platform-specific launcher in the repo root:

- **macOS**: `Launch_Eras_Zombie_Invasion.command`
- **Windows**: `Launch_Eras_Zombie_Invasion.bat`
- **Linux**: run `python3 launch_eras_zombie_invasion.py`

These launchers automatically point to the local `src/` folder so the game starts
seamlessly from a fresh download.

### Controls
- **1–8**: Switch active nation (all nations are controllable).
- **Left click**: Select a unit belonging to the active nation.
- **Right click**: Move the selected unit or assign workers to resource nodes.
- **S**: Train a soldier (requires a barracks).
- **W**: Train a worker.
- **R**: Research next tech tier.
- **B**: Enter barracks build mode (left click to place).
- **D**: Enter tower build mode (left click to place).
- **Esc**: Cancel build mode or exit after game over.

## Simulation Prototype
Run the text simulation to iterate on balance and AI tuning:

```bash
PYTHONPATH=src python -m eras_zombie_invasion.cli --ticks 60 --log-interval 10
```

The simulation models the eight nations, resource gathering, tech advancement, training
decisions, and escalating zombie pressure in 1-minute ticks.

## Vision
Build a standalone RTS that captures the cooperative/competitive tension of the original map, with modernized systems, readability, and scale. The design is intended to be engine-agnostic so that implementation can proceed in Unreal, Unity, Godot, or a custom engine.
