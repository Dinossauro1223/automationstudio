@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "PYTHONUTF8=1"
title Automation Studio - Testes

rem Atalho para rodar os testes. Duplo clique = suite completa. Em um terminal:
rem     Rodar_Testes.bat  rapido, completo, windows, repetir [N], cobertura, mutacoes, instalar ou ajuda
rem Qualquer coisa depois do modo vai para o executor de testes (ex.: Rodar_Testes.bat completo -k atalho -x).
rem O modo "windows" ENVIA teclado e mouse de verdade e pede confirmacao antes. Veja tests\README.md.

set "BASE=%~dp0"
set "AS_PY=3.14"
if exist "%BASE%python_version.txt" set /p AS_PY=<"%BASE%python_version.txt"

where py.exe >nul 2>&1
if errorlevel 1 (
    echo Python Launcher nao encontrado. Instale o Python %AS_PY% pelo python.org.
    pause
    exit /b 1
)
py.exe -%AS_PY% -c "import sys" >nul 2>&1
if errorlevel 1 (
    echo Python %AS_PY% nao encontrado. Instale-o ou ajuste python_version.txt.
    pause
    exit /b 1
)

set "AS_DUPLO_CLIQUE="
if "%~1"=="" set "AS_DUPLO_CLIQUE=1"

py.exe -%AS_PY% "%BASE%tests\testsupport\rodar_testes.py" %*
set "AS_CODIGO=%ERRORLEVEL%"

echo.
if "%AS_CODIGO%"=="0" (
    echo RESULTADO: OK
) else (
    echo RESULTADO: FALHOU ^(codigo %AS_CODIGO%^). O log esta na pasta logs.
)
if defined AS_DUPLO_CLIQUE pause
exit /b %AS_CODIGO%
