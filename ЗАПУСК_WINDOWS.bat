@echo off
chcp 65001 >nul
title Анализ оригинальности текста v2

cd /d "%~dp0"
set PYTHONPATH=%~dp0

echo ============================================
echo   Анализ оригинальности текста v2
echo   FastAPI + bge-m3 + rugpt3 + PostgreSQL
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден.
    echo Установите Python 3.10+ с https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/2] Создание виртуального окружения...
    python -m venv .venv
    if errorlevel 1 (
        echo [ОШИБКА] Не удалось создать .venv
        pause
        exit /b 1
    )
    del ".venv\.installed" 2>nul
)

set PYTHON=".venv\Scripts\python.exe"

if not exist ".venv\.installed" (
    echo [2/2] Установка библиотек (может занять 10-20 мин)...
    %PYTHON% install_deps.py
    if errorlevel 1 (
        echo [ОШИБКА] Не удалось установить зависимости.
        pause
        exit /b 1
    )
    echo. > ".venv\.installed"
) else (
    echo Библиотеки уже установлены.
)

if not exist ".env" (
    echo.
    echo [INFO] Создайте .env из .env.example
    copy /Y ".env.example" ".env" >nul 2>&1
)

echo.
echo [0/2] Проверка PostgreSQL (nikita2)...
%PYTHON% scripts\check_db.py
if errorlevel 1 (
    echo [ОШИБКА] Нет подключения к PostgreSQL. См. .env
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Запуск API + ML workers
echo   http://127.0.0.1:8001
echo   PostgreSQL + Qdrant (опционально)
echo   Остановка: Ctrl+C
echo ============================================
echo.

%PYTHON% run.py

echo.
echo Сервер остановлен.
pause
