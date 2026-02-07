from __future__ import annotations

import argparse

from .game import simulate_game


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a simulation of Eras Zombie Invasion.",
    )
    parser.add_argument("--ticks", type=int, default=60, help="Minutes to simulate.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument(
        "--log-interval",
        type=int,
        default=10,
        help="Minutes between summary output.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    output = simulate_game(args.ticks, args.seed, args.log_interval)
    print("\n".join(output))


if __name__ == "__main__":
    main()
