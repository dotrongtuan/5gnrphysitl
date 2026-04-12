@echo off
setlocal
powershell -ExecutionPolicy Bypass -File "%~dp0run_gui_radioconda.ps1" %*
