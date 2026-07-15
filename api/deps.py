from __future__ import annotations

from typing import AsyncGenerator

from database.pool import get_pool


async def get_db_pool():
    return get_pool()
