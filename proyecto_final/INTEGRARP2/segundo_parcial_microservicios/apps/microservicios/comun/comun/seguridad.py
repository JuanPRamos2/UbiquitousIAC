"""
Autenticación y autorización compartidas por todos los microservicios.

Decisión de diseño que conviene entender antes de leer el código:

El sistema web debe seguir funcionando de forma independiente, así que NO
se le quitó su propio inicio de sesión. En lugar de eso, el sistema web y
auth-service firman con el mismo secreto y comparten la misma instancia de
Redis. Las consecuencias son las que se quieren:

  - Un token emitido por auth-service sirve en el sistema web, y al revés.
  - Un cierre de sesión en cualquiera de los dos revoca en todos, porque
    la lista de revocados vive en Redis y no en la memoria de un proceso.
  - Si los microservicios se caen, el sistema web sigue operando.

Todo microservicio consulta Redis durante la autorización, que es un
requisito explícito del parcial: un JWT con firma válida no basta.
"""
import functools
import os

import jwt
import redis
from flask import current_app, g, request

from .errores import ErrorApi

JWT_SECRETO = os.environ.get("JWT_SECRETO") or (
    "secreto-solo-para-developer"
    if os.environ.get("APP_AMBIENTE", "developer") == "developer"
    else None)
JWT_ALGORITMO = "HS256"

_redis = None


def obtener_redis():
    global _redis
    if _redis is None:
        _redis = redis.Redis(
            host=os.environ.get("REDIS_HOST", "cache"),
            port=int(os.environ.get("REDIS_PUERTO", "6379")),
            socket_connect_timeout=2, decode_responses=True)
    return _redis


def leer_token() -> str:
    cabecera = request.headers.get("Authorization", "")
    if cabecera.startswith("Bearer "):
        return cabecera[7:].strip()
    # Se acepta también la cookie del sistema web, para que el navegador
    # pueda llamar a los microservicios sin duplicar el token.
    return request.cookies.get("bienestar_sesion", "")


def decodificar(token: str) -> dict:
    if not JWT_SECRETO:
        raise ErrorApi("CONFIGURACION", "Falta JWT_SECRETO en este ambiente", 500)
    try:
        return jwt.decode(token, JWT_SECRETO, algorithms=[JWT_ALGORITMO])
    except jwt.ExpiredSignatureError:
        raise ErrorApi("TOKEN_EXPIRADO",
                       "El token expiro. Renueva la sesion.", 401)
    except jwt.PyJWTError:
        raise ErrorApi("TOKEN_INVALIDO",
                       "El token no es valido.", 401)


def sesion_viva(jti: str) -> bool:
    """Un JWT con firma válida no basta: la sesión debe seguir activa.

    Si Redis no responde se rechaza. En el sistema web la decisión fue la
    contraria —degradar y seguir— porque ahí ya hay una sesión establecida
    y negar todo dejaria el portal inservible. Aqui, en cambio, se trata de
    servicios que atienden a clientes externos: ante la duda, no se abre.
    """
    r = obtener_redis()
    if r.exists(f"revocado:{jti}"):
        return False
    return bool(r.exists(f"sesion:{jti}"))


def requiere_token(f):
    """Valida firma, vigencia y sesión. Deja la identidad en g.actor."""
    @functools.wraps(f)
    def envoltura(*a, **kw):
        token = leer_token()
        if not token:
            raise ErrorApi("TOKEN_AUSENTE",
                           "Falta el encabezado Authorization: Bearer <token>.", 401)
        carga = decodificar(token)
        jti = carga.get("jti", "")
        try:
            if not sesion_viva(jti):
                raise ErrorApi("SESION_REVOCADA",
                               "La sesion fue cerrada o revocada.", 401)
        except ErrorApi:
            raise
        except Exception:
            current_app.logger.error("Redis no disponible al validar la sesion")
            raise ErrorApi("DEPENDENCIA_NO_DISPONIBLE",
                           "No se pudo verificar la sesion.", 503)
        g.actor = carga
        return f(*a, **kw)
    return envoltura


def requiere_permiso(*codigos):
    """Autorización por permiso, consultado en la base en cada petición.

    Los permisos NO viajan en el token a propósito: si viajaran, quitarle
    un permiso a un perfil no surtiría efecto hasta que caducaran todos los
    tokens emitidos.
    """
    def decorador(f):
        @functools.wraps(f)
        @requiere_token
        def envoltura(*a, **kw):
            from .datos import consultar
            filas = consultar(
                "SELECT p.codigo FROM usuarios.perfil_permiso pp "
                "JOIN usuarios.permiso p USING (permiso_id) WHERE pp.perfil_id = %s",
                (g.actor.get("perfil_id"),))
            g.permisos = {x["codigo"] for x in filas}
            if not set(codigos) & g.permisos:
                raise ErrorApi(
                    "SIN_PERMISO",
                    f"El perfil {g.actor.get('perfil')} no tiene ninguno de "
                    f"los permisos requeridos: {', '.join(codigos)}.", 403)
            return f(*a, **kw)
        return envoltura
    return decorador
