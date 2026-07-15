"""Установка зависимостей (вызывается из ЗАПУСК_WINDOWS.bat)."""
import subprocess
import sys


def main() -> int:
    py = sys.executable
    pip = [py, "-m", "pip"]

    print("Обновление pip...")
    subprocess.check_call(pip + ["install", "--upgrade", "pip"])

    print("Установка PyTorch (CPU)...")
    subprocess.check_call(
        pip
        + [
            "install",
            "torch",
            "--index-url",
            "https://download.pytorch.org/whl/cpu",
        ]
    )

    print("Установка библиотек из requirements.txt...")
    subprocess.check_call(pip + ["install", "-r", "requirements.txt"])

    print("\nOK: зависимости установлены.")
    print("Первый запуск workers скачает модели HuggingFace (~3-4 GB).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
