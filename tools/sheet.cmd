@echo off
rem Numbered contact sheet (_sheet.jpg) of a Screenshot Studio folder, opened when done.
rem   sheet.cmd [FS25_PX150XL]     no folder: lists them and asks
setlocal
set "FOLDER=%~1"
if not defined FOLDER call "%~dp0_py.cmd" studio
if not defined FOLDER set /p "FOLDER=Folder: "
if defined FOLDER call "%~dp0_py.cmd" sheet "%FOLDER%" --open
call "%~dp0_pause.cmd"
