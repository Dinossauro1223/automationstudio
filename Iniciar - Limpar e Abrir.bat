@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Automation Studio - Limpar e Abrir

set "BASE=%~dp0"
set "SCRIPT=%BASE%AutomationStudio.pyw"
set "LOGDIR=%BASE%logs"
set "LOG=%LOGDIR%\AutomationStudio.log"
set "AS_PY=3.14"
if exist "%BASE%python_version.txt" set /p AS_PY=<"%BASE%python_version.txt"

rem Os Pythons auxiliares abaixo (que escrevem no log) rodam em modo UTF-8: e o que o echo grava depois do chcp 65001.
set "PYTHONUTF8=1"

if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>&1
> "%LOG%" echo ============================================================
>>"%LOG%" echo AUTOMATION STUDIO - LIMPAR E ABRIR
>>"%LOG%" echo Data/hora: %date% %time%
>>"%LOG%" echo Pasta: %BASE%

echo [1/3] Encerrando processos relacionados...
>>"%LOG%" echo [1/3] Encerrando processos relacionados...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$names=@('AutomationStudio.pyw'); $procs=Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($names | ForEach-Object { $_.CommandLine -like ('*'+$_+'*') } | Where-Object { $_ }) }; foreach($p in $procs){ try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop; Write-Output ('Encerrado PID '+$p.ProcessId) } catch {} }" >>"%LOG%" 2>&1

echo [2/3] Verificando Python Launcher...
>>"%LOG%" echo [2/3] Verificando Python Launcher...
where py.exe >nul 2>&1
if errorlevel 1 (
    >>"%LOG%" echo ERRO: py.exe nao encontrado.
    echo Python Launcher nao encontrado.
    pause
    exit /b 1
)
py.exe -%AS_PY% -c "import sys; print(sys.executable)" >>"%LOG%" 2>&1
if errorlevel 1 (
    >>"%LOG%" echo ERRO: Python %AS_PY% nao encontrado no Launcher. Instale-o ou ajuste python_version.txt.
    echo Python %AS_PY% nao encontrado. Instale-o ou ajuste python_version.txt.
    pause
    exit /b 1
)

echo [3/3] Verificando dependencias e abrindo...
>>"%LOG%" echo [3/3] Verificando dependencias e abrindo...
py.exe -%AS_PY% -c "import PySide6, pynput; print('DEPENDENCIAS OK')" >>"%LOG%" 2>&1
if errorlevel 1 (
    >>"%LOG%" echo ERRO: dependencias ausentes para o Python %AS_PY%. Execute Instalar_Dependencias_Global.bat.
    echo Dependencias ausentes para o Python %AS_PY%. Execute Instalar_Dependencias_Global.bat.
    pause
    exit /b 1
)

set "PYTHONUTF8="
where pyw.exe >nul 2>&1
if not errorlevel 1 (
    >>"%LOG%" echo Iniciando via pyw.exe -%AS_PY%...
    start "" /b pyw.exe -%AS_PY% "%SCRIPT%"
) else (
    >>"%LOG%" echo pyw.exe nao encontrado; usando py.exe -%AS_PY%...
    start "" /b py.exe -%AS_PY% "%SCRIPT%"
)
>>"%LOG%" echo AutomationStudio.pyw solicitado diretamente.
exit /b 0
