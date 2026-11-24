"""
Autenticación con JWT, sesión en Redis y control de permisos.

Tres ideas sostienen este archivo:

1. El JWT viaja en una cookie HttpOnly. Guardarlo en localStorage lo dejaría
   al alcance de cualquier script de la página; en una cookie HttpOnly el
   JavaScript del navegador no puede leerlo.

2. Un JWT válido no basta. Cada petición consulta Redis: si el identificador
   del token está en la lista de revocados, o si su sesión ya no existe, se
   rechaza. Eso es lo que hace que un logout surta efecto de inmediato en
   lugar de esperar a que el token expire.

3. Los permisos NO se leen del token. El token dice quién eres; los permisos
   se consultan en la base en cada petición. Así, quitarle un permiso a un
   perfil surte efecto sin esperar a que caduquen los tokens emitidos.
"""
import datetime as dt
import functools
import uuid

import jwt
from flask import current_app, g, redirect, request, url_for

from .config import Config
from .datos import consultar, consultar_uno, obtener_redis

COOKIE = "bienestar_sesion"


# ---------------------------------------------------------------- emisión
def emitir_token(usuario_id: str, perfil_id: int, perfil: str, unidad_alcance):
    jti = uuid.uuid4().hex
    ahora = dt.datetime.now(dt.timezone.utc)
    carga = {
        "sub": usuario_id,
        "perfil_id": perfil_id,
        "perfil": perfil,
        "unidad_alcance": unidad_alcance,
        "jti": jti,
        "iat": ahora,
        "exp": ahora + dt.timedelta(minutes=Config.JWT_MINUTOS),
    }
    token = jwt.encode(carga, Config.JWT_SECRETO, algorithm=Config.JWT_ALGORITMO)

    # La sesión vive en Redis con la misma vigencia que el token.
    r = obtener_redis()
    r.hset(f"sesion:{jti}", mapping={
        "usuario_id": usuario_id, "perfil": perfil,
        "emitido": ahora.isoformat(),
    })
    r.expire(f"sesion:{jti}", Config.JWT_MINUTOS * 60)
    return token, jti


def revocar(jti: str):
    r = obtener_redis()
    r.setex(f"revocado:{jti}", Config.JWT_MINUTOS * 60, "1")
    r.delete(f"sesion:{jti}")


# ---------------------------------------------------------------- lectura
def sesion_actual():
    """Devuelve los datos de sesión o None. No lanza excepciones."""
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    try:
        carga = jwt.decode(token, Config.JWT_SECRETO, algorithms=[Config.JWT_ALGORITMO])
    except jwt.PyJWTError:
        return None

    jti = carga.get("jti", "")
    try:
        r = obtener_redis()
        if r.exists(f"revocado:{jti}"):
            return None
        if not r.exists(f"sesion:{jti}"):
            return None
    except Exception:
        # Redis caído: se acepta el token porque su firma y vigencia son
        # válidas, y se deja constancia. Es una degradación consciente:
        # negar todo dejaría el sistema inservible por una caché caída.
        current_app.logger.warning("Redis no disponible; no se pudo verificar revocación")
    return carga


def permisos_de(perfil_id: int):
    filas = consultar(
        "SELECT p.codigo FROM usuarios.perfil_permiso pp "
        "JOIN usuarios.permiso p USING (permiso_id) WHERE pp.perfil_id = %s",
        (perfil_id,))
    return {f["codigo"] for f in filas}


def cargar_usuario():
    """Se ejecuta antes de cada petición y deja la sesión en g."""
    g.sesion = sesion_actual()
    g.permisos = permisos_de(g.sesion["perfil_id"]) if g.sesion else set()


# ---------------------------------------------------------------- guardas
def requiere_sesion(f):
    @functools.wraps(f)
    def envoltura(*a, **kw):
        if not g.get("sesion"):
            return redirect(url_for("sesion.entrar", siguiente=request.path))
        return f(*a, **kw)
    return envoltura


def requiere_permiso(*codigos):
    """El permiso se valida en el servidor, nunca solo escondiendo el menú.

    Ocultar una opción del menú es comodidad para la persona; la validación
    real ocurre aquí, de modo que escribir la URL a mano tampoco funcione.
    """
    def decorador(f):
        @functools.wraps(f)
        def envoltura(*a, **kw):
            if not g.get("sesion"):
                return redirect(url_for("sesion.entrar", siguiente=request.path))
            if not set(codigos) & g.permisos:
                from .bitacora import registrar
                registrar("ACCESO_DENEGADO", "RECHAZADO_PERMISO",
                          recurso=request.path)
                return redirect(url_for("portal.inicio", denegado=1))
            return f(*a, **kw)
        return envoltura
    return decorador


# ------------------------------------------------- intentos fallidos
def contar_intento_fallido(correo: str) -> int:
    try:
        r = obtener_redis()
        clave = f"intentos:{correo.lower()}"
        n = r.incr(clave)
        if n == 1:
            r.expire(clave, Config.VENTANA_BLOQUEO)
        return n
    except Exception:
        return 0


def esta_bloqueado(correo: str) -> bool:
    try:
        n = obtener_redis().get(f"intentos:{correo.lower()}")
        return bool(n) and int(n) >= Config.INTENTOS_MAXIMOS
    except Exception:
        return False


def limpiar_intentos(correo: str):
    try:
        obtener_redis().delete(f"intentos:{correo.lower()}")
    except Exception:
        pass


def verificar_credenciales(correo: str, contrasena: str):
    """La comparación la hace PostgreSQL con crypt(), no Python.

    El hash nunca sale de la base, y crypt() compara en tiempo constante.
    """
    return consultar_uno(
        """
        SELECT u.usuario_id, u.nombre, u.apellido_paterno, u.correo,
               up.perfil_id, pf.nombre AS perfil, up.unidad_alcance_id
          FROM usuarios.usuario u
          JOIN usuarios.usuario_perfil up USING (usuario_id)
          JOIN usuarios.perfil pf USING (perfil_id)
         WHERE lower(u.correo) = lower(%s)
           AND u.activo
           AND u.contrasena_hash = crypt(%s, u.contrasena_hash)
        """, (correo, contrasena))
