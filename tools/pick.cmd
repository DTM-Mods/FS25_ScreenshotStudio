@echo off
rem Copies the chosen pictures (numbers from the sheet, hero shot first) into a repo: modhub\screenshots\ (ModHub,
rem 1600x900, unedited) and screenshots\ (README and dtmmods.com, 1920x1080). --no-modhub: screenshots\ only.
rem   pick.cmd FS25_PX150XL 4 11 2 [--align left]   into the mod repo with the folder's name
rem   pick.cmd                                     asks for folder, numbers, repo and alignment
setlocal
if not "%~1"=="" goto direct
call "%~dp0_py.cmd" studio
set /p "FOLDER=Folder: "
if not defined FOLDER exit /b 1
call "%~dp0_py.cmd" sheet "%FOLDER%" --open
set /p "NUMS=Numbers, hero shot first (e.g. 4 11 2): "
if not defined NUMS exit /b 1
set /p "REPO=Repo name or path [%FOLDER%]: "
if not defined REPO set "REPO=%FOLDER%"
set /p "ALIGN=Ultrawide crop left/center/right [center]: "
if not defined ALIGN set "ALIGN=center"
call "%~dp0_py.cmd" pick "%REPO%" "%FOLDER%" %NUMS% --align %ALIGN%
call "%~dp0_pause.cmd"
exit /b
:direct
call "%~dp0_py.cmd" pick %1 %*
exit /b %ERRORLEVEL%
