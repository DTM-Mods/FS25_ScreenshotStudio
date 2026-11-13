@echo off
rem Your newest game and Steam (F12) screenshots.
rem   new.cmd [YYYY-MM-DD]     default: the last 7 days
setlocal
set "SINCE=%~1"
if not defined SINCE for /f %%d in ('powershell -NoProfile -Command "(Get-Date).AddDays(-7).ToString('yyyy-MM-dd')"') do set "SINCE=%%d"
call "%~dp0_py.cmd" new --since %SINCE%
call "%~dp0_pause.cmd"
