"""Conexión a PostgreSQL. La fuente de verdad sigue siendo la base relacional."""
import os
from datetime import date, datetime
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor


def connect():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "5433")),
        dbname=os.getenv("DB_NAME", "library_db"),
        user=os.getenv("DB_USER", "library_user"),
        password=os.getenv("DB_PASSWORD", ""),
        connect_timeout=int(os.getenv("DB_CONNECT_TIMEOUT", "5")),
    )


def clean(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean(item) for item in value]
    return value


def query(sql, params=None, fetch="all"):
    conn = connect()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params or ())
                if fetch == "none":
                    return None
                if fetch == "one":
                    row = cur.fetchone()
                    return clean(dict(row)) if row else None
                return [clean(dict(row)) for row in cur.fetchall()]
    finally:
        conn.close()


def ping():
    row = query("SELECT 1 AS ok", fetch="one")
    return bool(row and row.get("ok") == 1)


def _statements(sql_text):
    chunks = []
    current = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if not current and (not stripped or stripped.startswith("--")):
            continue
        current.append(line)
        if stripped.endswith(";"):
            statement = "\n".join(current).strip().rstrip(";").strip()
            if statement and statement.upper() not in ("BEGIN", "COMMIT"):
                chunks.append(statement)
            current = []
    return chunks


def execute_script(sql_text):
    conn = connect()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            for statement in _statements(sql_text):
                cur.execute(statement)
    finally:
        conn.close()
