@echo off
setlocal
cd /d "%~dp0..\.."
for %%V in (3.12 3.13 3.11) do (
  py -%%V -c "import struct; assert struct.calcsize('P') == 8" >nul 2>&1
  if not errorlevel 1 (
    py -%%V -m scripts.windows.source %*
    goto result
  )
)
python -c "import sys,struct; assert (3,11) <= sys.version_info[:2] < (3,14); assert struct.calcsize('P') == 8" >nul 2>&1
if errorlevel 1 goto missing
python -m scripts.windows.source %*
:result
if errorlevel 1 goto failed
exit /b 0
:missing
echo Installez Python 3.12 64 bits depuis python.org, puis relancez ce fichier.
:failed
echo Le lancement ou la construction a echoue. Le message ci-dessus donne la cause.
pause
exit /b 1
