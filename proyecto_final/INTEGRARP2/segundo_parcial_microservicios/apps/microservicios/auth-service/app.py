"""
auth-service — autenticación y ciclo de vida de la sesión.

Responsabilidad única: emitir, renovar, validar y revocar tokens. No sabe
nada del negocio; no consulta encuestas ni agregados. Cualquier otro
servicio que necesite saber quién es el llamante usa la librería común,
que verifica la firma y consulta Redis, sin tener que llamar a este
servicio en cada petición.

Por qué el token de acceso dura 15 minutos y hay uno de renovación: un
token de acceso robado deja de servir pronto, y el de renovación se puede
revocar de golpe. Un token de acceso de larga duración no se puede
cancelar sin una lista negra enorme.
"""
import datetime as dt
import os
import uuid

import jwt
from flask import g, request

from comun import (ErrorApi, VERSION_API, crear_servicio, limite_consumo,
                   obtener_redis, responder, requiere_token)
from comun.datos import consultar_uno, ping as ping_pg
from comun.seguridad import JWT_ALGORITMO, JWT_SECRETO

MINUTOS_ACCESO = int(os.environ.get("JWT_MINUTOS", "15"))
DIAS_RENOVACION = int(os.environ.get("JWT_DIAS_RENOVACION", "7"))
INTENTOS_MAXIMOS = int(os.environ.get("INTENTOS_MAXIMOS", "5"))
VENTANA_BLOQUEO = int(os.environ.get("VENTANA_BLOQUEO", "900"))

os.environ.setdefault("NOMBRE_SERVICIO", "auth-service")


def _ping_redis():
    obtener_redis().ping()


app = crear_servicio(
    "auth-service",
    "Emite, renueva, valida y revoca tokens de acceso",
    comprobaciones={"postgresql": ping_pg, "redis": _ping_redis})

from contrato import montar as _montar_contrato
_montar_contrato(app)

BASE = f"/api/{VERSION_API}/auth"


# ------------------------------------------------------------ utilidades
def _emitir(usuario: dict):
    jti = uuid.uuid4().hex
    ahora = dt.datetime.now(dt.timezone.utc)
    acceso = jwt.encode({
        "sub": usuario["usuario_id"],
        "perfil_id": usuario["perfil_id"],
        "perfil": usuario["perfil"],
        "unidad_alcance": usuario["unidad_alcance_id"],
        "jti": jti, "tipo": "acceso",
        "iat": ahora, "exp": ahora + dt.timedelta(minutes=MINUTOS_ACCESO),
    }, JWT_SECRETO, algorithm=JWT_ALGORITMO)

    renovacion = jwt.encode({
        "sub": usuario["usuario_id"], "jti": jti, "tipo": "renovacion",
        "iat": ahora, "exp": ahora + dt.timedelta(days=DIAS_RENOVACION),
    }, JWT_SECRETO, algorithm=JWT_ALGORITMO)

    r = obtener_redis()
    r.hset(f"sesion:{jti}", mapping={
        "usuario_id": usuario["usuario_id"], "perfil": usuario["perfil"],
        "emitido": ahora.isoformat(), "origen": "auth-service"})
    # La sesion vive lo que el token de renovacion, no lo que el de acceso:
    # si expirara con el de acceso, renovar seria imposible.
    r.expire(f"sesion:{jti}", DIAS_RENOVACION * 86400)

    return {
        "token_acceso": acceso,
        "token_renovacion": renovacion,
        "tipo_token": "Bearer",
        "expira_en": MINUTOS_ACCESO * 60,
        "emitido_en": ahora.isoformat(),
        "usuario": {
            "usuario_id": usuario["usuario_id"],
            "nombre": f"{usuario['nombre']} {usuario['apellido_paterno']}",
            "correo": usuario["correo"],
            "perfil": usuario["perfil"],
            "perfil_id": usuario["perfil_id"],
            "unidad_alcance": usuario["unidad_alcance_id"],
        },
    }


def _bitacora(accion, resultado, actor=None, perfil=None, recurso=None):
    from comun.datos import cursor
    try:
        with cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO auditoria.bitacora (actor_usuario_id, actor_perfil, "
                " accion, tipo_recurso, recurso_id, resultado, correlacion_id, "
                " direccion_origen) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (actor, (perfil or "ANONIMO")[:30], accion, "USUARIO", recurso,
                 resultado, getattr(g, "correlacion_id", ""),
                 (request.headers.get("X-Forwarded-For", request.remote_addr) or "")
                 .split(",")[0].strip() or None))
    except Exception:
        app.logger.error("No se pudo escribir en la bitacora: %s/%s", accion, resultado)


# ---------------------------------------------------------------- rutas
@app.post(f"{BASE}/login")
def login():
    limite_consumo(maximo=30, ventana=60)
    cuerpo = request.get_json(silent=True) or {}
    correo = (cuerpo.get("correo") or "").strip()
    contrasena = cuerpo.get("contrasena") or ""

    faltantes = [c for c, v in (("correo", correo), ("contrasena", contrasena)) if not v]
    if faltantes:
        raise ErrorApi("CAMPOS_OBLIGATORIOS",
                       "Faltan campos obligatorios en la solicitud.", 400,
                       [{"campo": c, "problema": "requerido"} for c in faltantes])

    r = obtener_redis()
    clave_intentos = f"intentos:{correo.lower()}"
    try:
        if int(r.get(clave_intentos) or 0) >= INTENTOS_MAXIMOS:
            _bitacora("LOGIN_FALLIDO", "RECHAZADO", recurso=correo)
            raise ErrorApi("CUENTA_BLOQUEADA",
                           "Demasiados intentos fallidos. Intenta mas tarde.", 429)
    except ErrorApi:
        raise
    except Exception:
        pass

    usuario = consultar_uno(
        """
        SELECT u.usuario_id, u.nombre, u.apellido_paterno, u.correo,
               up.perfil_id, pf.codigo AS perfil, up.unidad_alcance_id
          FROM usuarios.usuario u
          JOIN usuarios.usuario_perfil up USING (usuario_id)
          JOIN usuarios.perfil pf USING (perfil_id)
         WHERE lower(u.correo) = lower(%s) AND u.activo
           AND u.contrasena_hash = crypt(%s, u.contrasena_hash)
        """, (correo, contrasena))

    if not usuario:
        try:
            n = r.incr(clave_intentos)
            if n == 1:
                r.expire(clave_intentos, VENTANA_BLOQUEO)
        except Exception:
            pass
        _bitacora("LOGIN_FALLIDO", "RECHAZADO", recurso=correo)
        # El mensaje no distingue correo inexistente de contrasena incorrecta:
        # hacerlo permitiria averiguar que correos existen.
        raise ErrorApi("CREDENCIALES_INVALIDAS",
                       "Correo o contrasena incorrectos.", 401)

    try:
        r.delete(clave_intentos)
    except Exception:
        pass

    datos = _emitir(usuario)
    _bitacora("LOGIN_EXITOSO", "EXITO", actor=usuario["usuario_id"],
              perfil=usuario["perfil"], recurso=usuario["usuario_id"])
    return responder(datos, 200, raiz="sesion")


@app.post(f"{BASE}/renovar")
def renovar():
    limite_consumo(maximo=60, ventana=60)
    cuerpo = request.get_json(silent=True) or {}
    token = cuerpo.get("token_renovacion") or ""
    if not token:
        raise ErrorApi("CAMPOS_OBLIGATORIOS", "Falta 'token_renovacion'.", 400,
                       [{"campo": "token_renovacion", "problema": "requerido"}])

    try:
        carga = jwt.decode(token, JWT_SECRETO, algorithms=[JWT_ALGORITMO])
    except jwt.ExpiredSignatureError:
        raise ErrorApi("TOKEN_EXPIRADO",
                       "El token de renovacion expiro. Inicia sesion de nuevo.", 401)
    except jwt.PyJWTError:
        raise ErrorApi("TOKEN_INVALIDO", "El token de renovacion no es valido.", 401)

    if carga.get("tipo") != "renovacion":
        # Un token de acceso NO sirve para renovar: si sirviera, robar uno
        # permitiria extender la sesion indefinidamente.
        raise ErrorApi("TIPO_DE_TOKEN_INCORRECTO",
                       "Se esperaba un token de renovacion.", 401)

    jti_viejo = carga.get("jti", "")
    r = obtener_redis()
    if r.exists(f"revocado:{jti_viejo}") or not r.exists(f"sesion:{jti_viejo}"):
        raise ErrorApi("SESION_REVOCADA", "La sesion ya no esta activa.", 401)

    usuario = consultar_uno(
        """
        SELECT u.usuario_id, u.nombre, u.apellido_paterno, u.correo,
               up.perfil_id, pf.codigo AS perfil, up.unidad_alcance_id
          FROM usuarios.usuario u
          JOIN usuarios.usuario_perfil up USING (usuario_id)
          JOIN usuarios.perfil pf USING (perfil_id)
         WHERE u.usuario_id = %s AND u.activo
        """, (carga.get("sub"),))
    if not usuario:
        raise ErrorApi("USUARIO_INACTIVO",
                       "El usuario ya no esta activo.", 401)

    # Rotacion: la sesion anterior se revoca al emitir la nueva. Asi, si
    # alguien robo el token de renovacion, su uso deja rastro y solo uno de
    # los dos (el legitimo o el atacante) conserva la sesion.
    r.setex(f"revocado:{jti_viejo}", DIAS_RENOVACION * 86400, "1")
    r.delete(f"sesion:{jti_viejo}")

    datos = _emitir(usuario)
    _bitacora("LOGIN_EXITOSO", "EXITO", actor=usuario["usuario_id"],
              perfil=usuario["perfil"], recurso="renovacion")
    return responder(datos, 200, raiz="sesion")


@app.post(f"{BASE}/logout")
@requiere_token
def logout():
    jti = g.actor.get("jti", "")
    r = obtener_redis()
    r.setex(f"revocado:{jti}", DIAS_RENOVACION * 86400, "1")
    r.delete(f"sesion:{jti}")
    _bitacora("LOGOUT", "EXITO", actor=g.actor.get("sub"),
              perfil=g.actor.get("perfil"), recurso=g.actor.get("sub"))
    return responder({"revocado": True, "jti": jti,
                      "mensaje": "La sesion quedo revocada en todos los componentes."},
                     200, raiz="logout")


@app.get(f"{BASE}/validar")
@requiere_token
def validar():
    """Permite a un cliente comprobar si su token sigue sirviendo."""
    return responder({
        "valido": True,
        "usuario_id": g.actor.get("sub"),
        "perfil": g.actor.get("perfil"),
        "perfil_id": g.actor.get("perfil_id"),
        "unidad_alcance": g.actor.get("unidad_alcance"),
        "jti": g.actor.get("jti"),
        "expira": g.actor.get("exp"),
    }, 200, raiz="validacion")


@app.get(f"{BASE}/permisos")
@requiere_token
def permisos():
    """Los permisos se consultan, no viajan en el token.

    Asi, revocarle un permiso a un perfil surte efecto de inmediato, sin
    esperar a que caduquen los tokens ya emitidos.
    """
    filas = consultar_uno(
        "SELECT array_agg(p.codigo ORDER BY p.codigo) AS codigos "
        "FROM usuarios.perfil_permiso pp JOIN usuarios.permiso p USING (permiso_id) "
        "WHERE pp.perfil_id = %s", (g.actor.get("perfil_id"),))
    return responder({"perfil": g.actor.get("perfil"),
                      "permisos": (filas or {}).get("codigos") or []},
                     200, raiz="permisos_respuesta")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PUERTO", "8101")))
