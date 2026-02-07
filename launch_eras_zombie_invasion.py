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
    subprocess.check_call([str(python_path), "-m", "pip", "install", "--upgrade", "pip"])
    subprocess.check_call([str(python_path), "-m", "pip", "install", "-e", str(repo_root)])


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    src_root = repo_root / "src"

    if os.environ.get("ERAS_BOOTSTRAPPED") != "1":
        python_path = _ensure_venv(repo_root)
        _install_requirements(python_path, repo_root)
        env = os.environ.copy()
        env["ERAS_BOOTSTRAPPED"] = "1"
        subprocess.check_call([str(python_path), str(__file__)], env=env)
        return

    if src_root.exists():
        sys.path.insert(0, str(src_root))
    runpy.run_module("eras_zombie_invasion", run_name="__main__")


if __name__ == "__main__":
    main()
