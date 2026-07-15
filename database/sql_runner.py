"""Выполнение SQL-файлов по одному оператору."""
from __future__ import annotations

import psycopg


def _strip_comments(sql: str) -> str:
    lines = []
    for line in sql.splitlines():
        if line.strip().startswith("--"):
            continue
        lines.append(line)
    return "\n".join(lines)


def split_sql(sql: str) -> list[str]:
    """Разбивает SQL на операторы, учитывая dollar-quoting ($$ и $tag$)."""
    sql = _strip_comments(sql)
    statements: list[str] = []
    current: list[str] = []
    i = 0
    n = len(sql)
    dollar_tag: str | None = None

    while i < n:
        ch = sql[i]

        if dollar_tag is None and ch == "$":
            j = i + 1
            while j < n and sql[j] != "$" and (sql[j].isalnum() or sql[j] == "_"):
                j += 1
            if j < n and sql[j] == "$":
                tag = sql[i + 1 : j]
                dollar_tag = tag
                current.append(sql[i : j + 1])
                i = j + 1
                continue

        if dollar_tag is not None:
            close = f"${dollar_tag}$"
            if sql.startswith(close, i):
                current.append(close)
                i += len(close)
                dollar_tag = None
                continue
            current.append(ch)
            i += 1
            continue

        if ch == ";":
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
            i += 1
            continue

        current.append(ch)
        i += 1

    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def run_sql_file(conn: psycopg.Connection, sql: str) -> None:
    for stmt in split_sql(sql):
        conn.execute(stmt)
