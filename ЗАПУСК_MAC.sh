#!/bin/bash
# macOS: chmod +x ЗАПУСК_MAC.sh && ./ЗАПУСК_MAC.sh

cd "$(dirname "$0")"

echo "============================================"
echo "  Анализ оригинальности текста"
echo "  macOS — TF-IDF + BM25 + веб-интерфейс"
echo "============================================"
echo

if ! command -v python3 &>/dev/null; then
    echo "[ОШИБКА] Python 3 не найден."
    echo
    echo "Установите Python 3.10+ с https://www.python.org/downloads/"
    echo "или через Homebrew: brew install python"
    echo
    read -r -p "Нажмите Enter для выхода..."
    exit 1
fi

echo "Python: $(python3 --version)"
echo

PYTHON=".venv/bin/python"

if [ ! -f "$PYTHON" ]; then
    echo "[1/2] Создание виртуального окружения..."
    python3 -m venv .venv || {
        echo "[ОШИБКА] Не удалось создать .venv"
        read -r -p "Нажмите Enter для выхода..."
        exit 1
    }
    rm -f ".venv/.installed"
fi

if [ ! -f ".venv/.installed" ]; then
    echo "[2/2] Установка библиотек..."
    echo "      Первый запуск может занять несколько минут."
    echo
    "$PYTHON" install_deps.py || {
        echo
        echo "[ОШИБКА] Не удалось установить зависимости."
        echo "Проверьте подключение к интернету и повторите запуск."
        read -r -p "Нажмите Enter для выхода..."
        exit 1
    }
    touch ".venv/.installed"
else
    echo "Библиотеки уже установлены. Пропуск установки."
    echo "Для переустановки удалите папку .venv"
fi

echo
echo "============================================"
echo "  Запуск веб-сервера..."
echo "  Браузер откроется автоматически."
echo "  Адрес: http://127.0.0.1:5000"
echo "  Остановка: Ctrl+C"
echo "============================================"
echo

(sleep 2 && open "http://127.0.0.1:5000") &

"$PYTHON" app.py

echo
echo "Сервер остановлен."
read -r -p "Нажмите Enter для выхода..."
