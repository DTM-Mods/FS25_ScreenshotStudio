@echo off
rem The three offline test suites: the mod (needs Python lupa: pip install --user lupa), fs25_screenshots.py, fs25_run_game.py.
setlocal
call "%~dp0_py.cmd" --test
set "RC=%ERRORLEVEL%"
call "%~dp0_pause.cmd"
exit /b %RC%
