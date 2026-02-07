#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import runpy
import subprocess
import sys
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    src_root = repo_root / "src"
    if src_root.exists():
        sys.path.insert(0, str(src_root))
    if importlib.util.find_spec("pygame") is None:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", str(repo_root)],
            check=True,
        )
    runpy.run_module("eras_zombie_invasion", run_name="__main__")


if __name__ == "__main__":
    main()
