@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Automation Studio - Dependencias Globais

set "LOG=%~dp0logs\AutomationStudio.log"
if not exist "%~dp0logs" mkdir "%~dp0logs" >nul 2>&1
set "AS_PY=3.14"
if exist "%~dp0python_version.txt" set /p AS_PY=<"%~dp0python_version.txt"

rem O Python e o pip escrevem no log em modo UTF-8, igual ao echo depois do chcp 65001 (log sem codificacao misturada).
set "PYTHONUTF8=1"

> "%LOG%" echo ============================================================
echo AUTOMATION STUDIO - DEPENDENCIAS GLOBAIS >> "%LOG%"
echo Inicio: %date% %time% >> "%LOG%"
echo ============================================================ >> "%LOG%"

echo.
echo ============================================================
echo   AUTOMATION STUDIO - DEPENDENCIAS GLOBAIS
echo ============================================================
echo.
echo Este instalador NAO cria .env e NAO depende do Automation Studio.
echo As bibliotecas serao instaladas no Python global do Windows.
echo.

set "PYEXE="
where py.exe >nul 2>&1
if not errorlevel 1 (
    py.exe -%AS_PY% -c "import sys; print(sys.executable)" >> "%LOG%" 2>&1
    if not errorlevel 1 set "PYEXE=py.exe -%AS_PY%"
)

if not defined PYEXE (
    where python.exe >nul 2>&1
    if not errorlevel 1 (
        for /f "tokens=1,2 delims=." %%A in ("%AS_PY%") do (
            python.exe -c "import sys; sys.exit(0 if sys.version_info[:2]==(%%A,%%B) else 1)" >nul 2>&1
        )
        if not errorlevel 1 set "PYEXE=python.exe"
    )
)

if not defined PYEXE (
    echo ERRO: Python global nao foi encontrado.
    echo ERRO: Python global nao foi encontrado. >> "%LOG%"
    echo.
    echo Instale o Python %AS_PY% para Windows com o Python Launcher, ou ajuste python_version.txt.
    pause
    exit /b 1
)

echo Python selecionado: %PYEXE%
echo Python selecionado: %PYEXE% >> "%LOG%"

echo.
echo Verificando pip...
%PYEXE% -m pip --version >> "%LOG%" 2>&1
if errorlevel 1 (
    echo Pip ausente. Tentando habilitar com ensurepip...
    %PYEXE% -m ensurepip --upgrade >> "%LOG%" 2>&1
    if errorlevel 1 goto :ERROR
)

echo.
echo Instalando/verificando PySide6...
%PYEXE% -m pip install "PySide6>=6.8" >> "%LOG%" 2>&1
if errorlevel 1 goto :ERROR

echo Instalando/verificando pynput...
%PYEXE% -m pip install "pynput>=1.7.7" >> "%LOG%" 2>&1
if errorlevel 1 goto :ERROR

echo Instalando/verificando PyInstaller...
%PYEXE% -m pip install "pyinstaller>=6.10" >> "%LOG%" 2>&1
if errorlevel 1 goto :ERROR

echo.
echo Testando importacoes...
%PYEXE% -c "import PySide6, pynput; print('DEPENDENCIAS OK')" >> "%LOG%" 2>&1
if errorlevel 1 goto :ERROR

echo.
echo ============================================================
echo   DEPENDENCIAS GLOBAIS PRONTAS
echo ============================================================
echo.
echo Nenhuma .env foi criada.
echo.
echo Log: %LOG%
echo.
echo Concluido: %date% %time% >> "%LOG%"
pause
exit /b 0

:ERROR
echo.
echo ============================================================
echo   ERRO AO PREPARAR AS DEPENDENCIAS
echo ============================================================
echo.
echo Consulte:
echo %LOG%
echo.
echo Se algum pacote nao existir para o Python %AS_PY%, o log mostra qual.
echo Falha: %date% %time% >> "%LOG%"
pause
exit /b 1
