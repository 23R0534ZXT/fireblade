@echo off
setlocal
set "TIMELINE_EXE=%~dp0TimelineNext.exe"
if not exist "%TIMELINE_EXE%" set "TIMELINE_EXE=%~dp0dist\TimelineNext\TimelineNext.exe"
if not exist "%TIMELINE_EXE%" (
  echo Executable absent. Lancez d'abord Construire-Windows.cmd.
  pause
  exit /b 1
)
set "TIMELINE_REPORT_DIR=%LOCALAPPDATA%\TimelineNext\Verifications"
if not defined LOCALAPPDATA set "TIMELINE_REPORT_DIR=%TEMP%\TimelineNext\Verifications"
if not exist "%TIMELINE_REPORT_DIR%" mkdir "%TIMELINE_REPORT_DIR%"
set "TIMELINE_REPORT=%TIMELINE_REPORT_DIR%\controle-%RANDOM%-%RANDOM%.json"
start "" /wait "%TIMELINE_EXE%" --self-test-report "%TIMELINE_REPORT%"
if errorlevel 1 (
  echo Verification echouee. Consultez le rapport et le journal de demarrage.
) else (
  echo Verification terminee. Le rapport indique les controles reellement executes.
)
echo Rapport : "%TIMELINE_REPORT%"
pause
