# Text Originality Detector

FastAPI-сервис проверки оригинальности студенческих работ:
сравнение с документами в PostgreSQL, глубокое заимствование (bge-m3),
копирование (TF-IDF + BM25), детекция ИИ (rugpt3).

## Состав

- `api/` — FastAPI (аналитика, задачи, файлы)
- `detector/` — ML-пайплайн
- `workers/` — ML-воркеры очереди
- `database/` — PostgreSQL
- `services/` — модуль аналитики
- `sql/` — схема БД
- `templates/` — веб-UI
- `config/` — настройки
- `run.py` — точка входа

## Запуск (Windows)

1. PostgreSQL, база `nikita2` (см. `DATABASE_URL` в `.env.example`)
2. `python -m venv .venv` и активация
3. `pip install -r requirements.txt`
4. скопировать `env.example` → `.env` и заполнить
5. API: `python -m uvicorn api.main:app --host 127.0.0.1 --port 8001`
6. воркер: `python -m workers.ml_worker 1`

UI: http://127.0.0.1:8001/

Или `ЗАПУСК_WINDOWS.bat`.
