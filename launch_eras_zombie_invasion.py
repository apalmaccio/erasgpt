#!/usr/bin/env python3
from __future__ import annotations

import os
import runpy
import subprocess
import sys
from pathlib import Path


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _ensure_venv(repo_root: Path) -> Path:
    venv_dir = repo_root / ".venv"
    python_path = _venv_python(venv_dir)
    if python_path.exists():
        return python_path
    import venv

    print("[Eras Zombie Invasion] Creating local .venv...")
    builder = venv.EnvBuilder(with_pip=True)
    builder.create(venv_dir)
    return python_path


def _install_requirements(python_path: Path, repo_root: Path) -> None:
    print("[Eras Zombie Invasion] Installing dependencies...")
    subprocess.check_call(
        [str(python_path), "-m", "pip", "install", "--upgrade", "pip"],
        cwd=str(repo_root),
    )
    subprocess.check_call(
        [str(python_path), "-m", "pip", "install", "-e", str(repo_root)],
        cwd=str(repo_root),
    )


def _can_run_game(python_path: Path, repo_root: Path) -> bool:
    """Return True if pygame and the game module are importable."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")
    result = subprocess.run(
        [str(python_path), "-c", "import pygame; import eras_zombie_invasion"],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        timeout=30,
    )
    return result.returncode == 0


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    src_root = repo_root / "src"

    if os.environ.get("ERAS_BOOTSTRAPPED") != "1":
        print("[Eras Zombie Invasion] Checking setup (first launch may install dependencies)...")
        python_path = _ensure_venv(repo_root)
        _install_requirements(python_path, repo_root)
        if not _can_run_game(python_path, repo_root):
            print("[Eras Zombie Invasion] Verifying install failed, retrying install...")
            _install_requirements(python_path, repo_root)
            if not _can_run_game(python_path, repo_root):
                print("[Eras Zombie Invasion] Setup failed. Please ensure Python 3.10+ and internet are available.")
                input("Press Enter to close.")
                sys.exit(1)
        env = os.environ.copy()
        env["ERAS_BOOTSTRAPPED"] = "1"
        subprocess.check_call([str(python_path), str(__file__)], env=env)
        return

    if src_root.exists():
        sys.path.insert(0, str(src_root))
    runpy.run_module("eras_zombie_invasion", run_name="__main__")


if __name__ == "__main__":
    main()
