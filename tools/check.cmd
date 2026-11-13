@echo off
rem At least 3 screenshots, all 1920x1080, in a repo's screenshots\ folder.
rem   check.cmd [FS25_PX150XL]     repo name or path; none: asks
setlocal
set "REPO=%~1"
if not defined REPO set /p "REPO=Repo name or path: "
if not defined REPO exit /b 1
call "%~dp0_py.cmd" check "%REPO%"
set "RC=%ERRORLEVEL%"
call "%~dp0_pause.cmd"
exit /b %RC%
