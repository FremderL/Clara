@echo off
setlocal
pushd "%~dp0" || exit /b 1
py "%~dp0viernes.py" --mode gui
popd
