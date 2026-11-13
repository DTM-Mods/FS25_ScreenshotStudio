@echo off
rem Starts the game with a savegame, takes the pictures of a plan, ends the game (fs25_run_game.py).
rem   run-game.cmd 1 --plan orbit       savegame1, the orbit plan
rem   run-game.cmd                      lists the saves and plans and asks
setlocal
if not "%~1"=="" goto direct
call "%~dp0_py.cmd" --run saves
echo.
call "%~dp0_py.cmd" --run plans
echo.
set /p "SAVE=Savegame number: "
if not defined SAVE exit /b 1
set /p "PLAN=Plan [smoke]: "
if not defined PLAN set "PLAN=smoke"
set /p "TARGET=What to photograph, part of its name [what you stand next to]: "
rem an empty "" would end _py.cmd's argument list, so --target only with a name
set "SS_TARGET="
if defined TARGET set SS_TARGET=--target "%TARGET%"
call "%~dp0_py.cmd" --run run %SAVE% --plan %PLAN% %SS_TARGET% --sheet
call "%~dp0_pause.cmd"
exit /b
:direct
call "%~dp0_py.cmd" --run run %*
exit /b %ERRORLEVEL%
