"""Acceso a PostgreSQL y a Redis.

Un solo lugar abre conexiones. Las vistas nunca arman SQL por concatenación:
todas las consultas de este archivo y de las rutas usan parámetros, que es lo
que impide la inyección de SQL.
"""
import contextlib

import psycopg2
import psycopg2.extras
import redis
from psycopg2 import pool

from .config import Config

_pool = None
_redis = None


def obtener_pool():
    global _pool
    if _pool is None:
        _pool = pool.ThreadedConnectionPool(Config.PG_POOL_MIN, Config.PG_POOL_MAX, Config.dsn())
    return _pool


def obtener_redis():
    global _redis
    if _redis is None:
        _redis = redis.Redis(host=Config.REDIS_HOST, port=Config.REDIS_PUERTO,
                             socket_connect_timeout=2, decode_responses=True)
    return _redis


@contextlib.contextmanager
def cursor(commit: bool = False):
    """Entrega un cursor que devuelve diccionarios y siempre regresa la conexión."""
    p = obtener_pool()
    cn = p.getconn()
    try:
        with cn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        if commit:
            cn.commit()
        else:
            cn.rollback()
    except Exception:
        cn.rollback()
        raise
    finally:
        p.putconn(cn)


def consultar(sql, params=None):
    with cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()


def consultar_uno(sql, params=None):
    with cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchone()


def ejecutar(sql, params=None):
    with cursor(commit=True) as cur:
        cur.execute(sql, params or ())
        return cur.fetchone() if cur.description else None
