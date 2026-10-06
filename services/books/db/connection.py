import logging
import psycopg2
from psycopg2.extras import RealDictCursor

from config import settings

logger = logging.getLogger(__name__)


def get_connection():
    return psycopg2.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        dbname=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        connect_timeout=10,
    )


def fetch_all(sql, params=None):
    conn = get_connection()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params or ())
                return cur.fetchall()
    finally:
        conn.close()


def fetch_one(sql, params=None):
    conn = get_connection()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params or ())
                return cur.fetchone()
    finally:
        conn.close()


def execute_in_transaction(callback):
    conn = get_connection()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                return callback(cur)
    except Exception:
        logger.exception("Error de PostgreSQL; se aplica rollback")
        raise
    finally:
        conn.close()
