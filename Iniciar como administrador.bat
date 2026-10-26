@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Automation Studio - Administrador

REM Opcao adicional para aplicativos de maior rigidez.
REM O uso normal nao depende deste arquivo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~dp0Iniciar.bat' -Verb RunAs"
exit /b 0
