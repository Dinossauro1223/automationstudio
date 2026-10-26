@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Automation Studio

set "BASE=%~dp0"
set "SCRIPT=%BASE%AutomationStudio.pyw"
set "LOGDIR=%BASE%logs"
set "LOG=%LOGDIR%\AutomationStudio.log"
set "AS_PY=3.14"
if exist "%BASE%python_version.txt" set /p AS_PY=<"%BASE%python_version.txt"

rem Os Pythons auxiliares abaixo (que escrevem no log) rodam em modo UTF-8: e o que o echo grava depois do chcp 65001.
rem Sem isto o log mistura duas codificacoes e uma pasta com acento no nome (ex.: usuario com c cedilha) fica ilegivel.
set "PYTHONUTF8=1"

if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>&1
> "%LOG%" echo ============================================================
>>"%LOG%" echo AUTOMATION STUDIO - NOVA EXECUCAO
>>"%LOG%" echo Data/hora: %date% %time%
>>"%LOG%" echo Pasta: %BASE%

if not exist "%SCRIPT%" (
    >>"%LOG%" echo ERRO: AutomationStudio.pyw nao encontrado.
    echo AutomationStudio.pyw nao encontrado.
    pause
    exit /b 1
)
where py.exe >nul 2>&1
if errorlevel 1 (
    >>"%LOG%" echo ERRO: py.exe nao encontrado.
    echo Python Launcher nao encontrado.
    pause
    exit /b 1
)

>>"%LOG%" echo Python solicitado: %AS_PY% (definido em python_version.txt)
>>"%LOG%" echo Python selecionado pelo Launcher:
py.exe -%AS_PY% -c "import sys; print(sys.executable)" >>"%LOG%" 2>&1
if errorlevel 1 (
    >>"%LOG%" echo ERRO: Python %AS_PY% nao encontrado no Launcher. Instale-o ou ajuste python_version.txt.
    echo Python %AS_PY% nao encontrado. Instale-o ou ajuste python_version.txt.
    pause
    exit /b 1
)

>>"%LOG%" echo Verificando PySide6 e pynput...
py.exe -%AS_PY% -c "import PySide6, pynput; print('DEPENDENCIAS OK')" >>"%LOG%" 2>&1
if errorlevel 1 (
    >>"%LOG%" echo ERRO: dependencias ausentes para o Python %AS_PY%. Execute Instalar_Dependencias_Global.bat.
    echo Dependencias ausentes para o Python %AS_PY%. Execute Instalar_Dependencias_Global.bat.
    pause
    exit /b 1
)

rem O programa abre pelo pyw.exe (Python sem janela de terminal). O caminho do Python nao e mais copiado para uma
rem variavel: com acento na pasta do usuario o cmd entendia o caminho errado e dizia que o pythonw.exe nao existia.
set "PYTHONUTF8="
where pyw.exe >nul 2>&1
if not errorlevel 1 (
    >>"%LOG%" echo Iniciando via pyw.exe -%AS_PY%...
    start "Automation Studio" /b pyw.exe -%AS_PY% "%SCRIPT%"
) else (
    >>"%LOG%" echo AVISO: pyw.exe nao encontrado; usando py.exe -%AS_PY%. A janela do terminal fica aberta enquanto o programa roda.
    start "Automation Studio" /b py.exe -%AS_PY% "%SCRIPT%"
)

>>"%LOG%" echo Bootstrap solicitado. O diagnostico de importacao/excecao tambem sera gravado pelo AutomationStudio.pyw.
exit /b 0
