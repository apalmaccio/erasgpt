@echo off
setlocal
cd /d "%~dp0"

if exist "%~dp0Launch_Eras_Zombie_Invasion.ps1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Launch_Eras_Zombie_Invasion.ps1"
) else (
  py -3 launch_eras_zombie_invasion.py
)
