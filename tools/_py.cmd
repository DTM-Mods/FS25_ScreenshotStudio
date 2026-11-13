@echo off
rem Runs fs25_screenshots.py (--run: fs25_run_game.py; --test: the offline tests) with py, or python if there is no py.
rem shift also moves %0, so the folder is kept before any shift
set "SS_DIR=%~dp0"
where py >nul 2>&1 && set "SS_PY=py -3" || set "SS_PY=python"
if "%~1"=="--test" goto test
if "%~1"=="--run" goto rungame
%SS_PY% "%~dp0fs25_screenshots.py" %*
exit /b
:rungame
shift
set "SS_ARGS="
:collect
if "%~1"=="" goto go
set SS_ARGS=%SS_ARGS% %1
shift
goto collect
:go
%SS_PY% "%SS_DIR%fs25_run_game.py" %SS_ARGS%
exit /b
:test
set "SS_RC=0"
for %%t in (test_screenshot_studio test_screenshots_tool test_run_game) do (
  echo === %%t
  %SS_PY% "%~dp0..\tests\%%t.py" || set "SS_RC=1"
  echo.
)
exit /b %SS_RC%
