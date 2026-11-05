@echo off
rem Fireblade 0.3.0 (branche locale hermes/ui-0.3.0, non poussee)
rem Ouvre la version du depot avec son environnement Python, sans passer par l'exe.
cd /d "%~dp0"
start "" "%~dp0.venv\Scripts\python.exe" -m fireblade %*
