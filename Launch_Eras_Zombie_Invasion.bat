@echo off
setlocal
cd /d "%~dp0"

REM Find Python: try py launcher, then python3, then python
set "PYTHON="
where py >nul 2>&1 && set "PYTHON=py -3"
if not defined PYTHON where python3 >nul 2>&1 && set "PYTHON=python3"
if not defined PYTHON where python >nul 2>&1 && set "PYTHON=python"

if not defined PYTHON (
    echo.
    echo [Eras Zombie Invasion] Python was not found.
    echo Please install Python 3.10 or newer from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

%PYTHON% launch_eras_zombie_invasion.py
if errorlevel 1 (
    echo.
    echo [Eras Zombie Invasion] The game exited with an error. See above for details.
    pause
    exit /b 1
)
