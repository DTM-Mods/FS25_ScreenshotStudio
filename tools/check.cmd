@echo off
rem The ModHub set in a repo's modhub\screenshots\ folder: at least 3, all 1600x900, unedited; lists screenshots\ too.
rem   check.cmd [FS25_PX150XL]     repo name or path; none: asks
setlocal
set "REPO=%~1"
if not defined REPO set /p "REPO=Repo name or path: "
if not defined REPO exit /b 1
call "%~dp0_py.cmd" check "%REPO%"
set "RC=%ERRORLEVEL%"
call "%~dp0_pause.cmd"
exit /b %RC%
