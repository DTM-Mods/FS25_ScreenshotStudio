@echo off
rem What Screenshot Studio has taken, per mod; with a folder name: the pictures in it, numbered.
rem   studio.cmd [FS25_PX150XL]
setlocal
call "%~dp0_py.cmd" studio %*
call "%~dp0_pause.cmd"
