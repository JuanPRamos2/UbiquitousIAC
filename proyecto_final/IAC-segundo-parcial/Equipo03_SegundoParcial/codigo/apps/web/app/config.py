"""Configuración del sistema web. Todo por variables de entorno."""
import os


def _obligatoria(nombre: str) -> str:
    v = os.environ.get(nombre)
    if not v:
        raise RuntimeError(f"Falta la variable de entorno {nombre}")
    return v


class Config:
    AMBIENTE = os.environ.get("APP_AMBIENTE", "developer")

    PG_HOST = os.environ.get("PG_HOST", "datos")
    PG_PUERTO = int(os.environ.get("PG_PUERTO", "5432"))
    PG_BASE = os.environ.get("PG_BASE", "bienestar")
    PG_USUARIO = os.environ.get("PG_USUARIO", "bienestar_app")
    PG_CLAVE = _obligatoria("PG_CLAVE")
    PG_POOL_MIN = int(os.environ.get("PG_POOL_MIN", "1"))
    PG_POOL_MAX = int(os.environ.get("PG_POOL_MAX", "8"))

    REDIS_HOST = os.environ.get("REDIS_HOST", "cache")
    REDIS_PUERTO = int(os.environ.get("REDIS_PUERTO", "6379"))

    # JWT. En developer hay un valor por omisión para que el equipo pueda
    # levantar el sistema sin configurar nada; fuera de developer la falta
    # de esta variable detiene el arranque a propósito.
    JWT_SECRETO = os.environ.get("JWT_SECRETO") or (
        "secreto-solo-para-developer" if AMBIENTE == "developer" else _obligatoria("JWT_SECRETO")
    )
    JWT_ALGORITMO = "HS256"
    JWT_MINUTOS = int(os.environ.get("JWT_MINUTOS", "15"))

    INTENTOS_MAXIMOS = int(os.environ.get("INTENTOS_MAXIMOS", "5"))
    VENTANA_BLOQUEO = int(os.environ.get("VENTANA_BLOQUEO", "900"))

    NIVEL_BITACORA = os.environ.get("NIVEL_BITACORA", "INFO")
    MOSTRAR_ERRORES = os.environ.get("MOSTRAR_ERRORES", "false").lower() == "true"

    @classmethod
    def dsn(cls) -> str:
        return (f"host={cls.PG_HOST} port={cls.PG_PUERTO} dbname={cls.PG_BASE} "
                f"user={cls.PG_USUARIO} password={cls.PG_CLAVE} "
                f"application_name=bienestar-web-{cls.AMBIENTE}")
