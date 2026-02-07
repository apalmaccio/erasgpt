"""Prototype simulation package for Eras Zombie Invasion."""

from .game import GameState, Nation, Resources, ZombieAI, create_default_game

__all__ = [
    "GameState",
    "Nation",
    "Resources",
    "ZombieAI",
    "create_default_game",
]
