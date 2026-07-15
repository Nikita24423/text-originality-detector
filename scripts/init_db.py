"""Применить схему БД (то же что scripts/check_db.py)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.check_db import main

if __name__ == "__main__":
    raise SystemExit(main())
