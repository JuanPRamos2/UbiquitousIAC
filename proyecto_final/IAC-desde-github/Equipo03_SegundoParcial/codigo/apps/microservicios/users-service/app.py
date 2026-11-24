"""
users-service — administración de usuarios, perfiles y permisos.

Responsabilidad única: quién existe en el sistema y qué perfil tiene. No
emite tokens (eso es de auth-service) ni toca datos de bienestar.

Una regla atraviesa todo este servicio: administrar usuarios NO da acceso
al contenido de las respuestas. El perfil Administrador puede crear
usuarios y asignar perfiles, y sigue sin poder leer un autorreporte,
porque el rol de base de datos con el que se conecta este servicio no
tiene permiso de lectura sobre ese esquema. La separación no depende de
que este código se porte bien.
"""
import os
import re

from flask import g, request

from comun import (ErrorApi, VERSION_API, crear_servicio,
                   cuerpo_peticion, limite_consumo,
                   obtener_redis, pagina, responder, requiere_permiso,
                   requiere_token, sobre_pagina)
from comun.datos import consultar, consultar_uno, cursor, ping as ping_pg

os.environ.setdefault("NOMBRE_SERVICIO", "users-service")

CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def _ping_redis():
    obtener_redis().ping()


app = crear_servicio(
    "users-service",
    "Administra usuarios, perfiles, permisos y alcance organizacional",
    comprobaciones={"postgresql": ping_pg, "redis": _ping_redis})

from contrato import montar as _montar_contrato
_montar_contrato(app)

BASE = f"/api/{VERSION_API}/usuarios"


def _bitacora(accion, resultado, recurso=None, tipo="USUARIO"):
    try:
        with cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO auditoria.bitacora (actor_usuario_id, actor_perfil, "
                " accion, tipo_recurso, recurso_id, resultado, correlacion_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                ((g.get("actor") or {}).get("sub"),
                 ((g.get("actor") or {}).get("perfil") or "ANONIMO")[:30],
                 accion, tipo, recurso, resultado,
                 getattr(g, "correlacion_id", "")))
    except Exception:
        app.logger.error("No se pudo escribir en la bitacora: %s", accion)


def _validar_alta(cuerpo, exigir_contrasena=True):
    """Validación de entrada. Devuelve la lista de problemas, no lanza.

    Se devuelven TODOS los problemas de una vez y no solo el primero: un
    formulario que corrige un error por intento es penoso de usar.
    """
    problemas = []
    uid = (cuerpo.get("usuario_id") or "").strip().upper()
    correo = (cuerpo.get("correo") or "").strip()
    nombre = (cuerpo.get("nombre") or "").strip()
    apellido = (cuerpo.get("apellido_paterno") or "").strip()
    contrasena = cuerpo.get("contrasena") or ""
    perfil_id = cuerpo.get("perfil_id")

    if not re.match(r"^USR-\d{5}$", uid):
        problemas.append({"campo": "usuario_id",
                          "problema": "debe tener la forma USR-00000"})
    if not CORREO.match(correo):
        problemas.append({"campo": "correo", "problema": "no es un correo valido"})
    if len(nombre) < 2:
        problemas.append({"campo": "nombre", "problema": "minimo 2 caracteres"})
    if len(apellido) < 2:
        problemas.append({"campo": "apellido_paterno", "problema": "minimo 2 caracteres"})
    if exigir_contrasena and len(contrasena) < 8:
        problemas.append({"campo": "contrasena", "problema": "minimo 8 caracteres"})
    if not isinstance(perfil_id, int):
        problemas.append({"campo": "perfil_id", "problema": "debe ser un entero"})
    return problemas


# ------------------------------------------------------------- listados
@app.get(BASE)
@requiere_permiso("USUARIO_ADMIN")
def listar():
    limite_consumo()
    p, t = pagina()
    busqueda = (request.args.get("busqueda") or "").strip()
    perfil = request.args.get("perfil_id")
    activo = request.args.get("activo")

    filtros, params = ["1=1"], []
    if busqueda:
        filtros.append("(u.nombre ILIKE %s OR u.apellido_paterno ILIKE %s "
                       "OR u.correo ILIKE %s OR u.usuario_id ILIKE %s)")
        params += [f"%{busqueda}%"] * 4
    if perfil:
        try:
            params.append(int(perfil))
            filtros.append("up.perfil_id = %s")
        except ValueError:
            raise ErrorApi("PARAMETRO_INVALIDO", "'perfil_id' debe ser entero.", 400)
    if activo in ("true", "false"):
        filtros.append("u.activo = %s")
        params.append(activo == "true")

    donde = " AND ".join(filtros)
    total = consultar_uno(
        f"SELECT count(*) AS n FROM usuarios.usuario u "
        f"LEFT JOIN usuarios.usuario_perfil up USING (usuario_id) WHERE {donde}",
        tuple(params))["n"]

    filas = consultar(
        f"""
        SELECT u.usuario_id, u.nombre, u.apellido_paterno, u.apellido_materno,
               u.correo, u.activo, u.fecha_ultimo_acceso,
               up.perfil_id, pf.nombre AS perfil, up.unidad_alcance_id
          FROM usuarios.usuario u
          LEFT JOIN usuarios.usuario_perfil up USING (usuario_id)
          LEFT JOIN usuarios.perfil pf USING (perfil_id)
         WHERE {donde}
         ORDER BY u.usuario_id
         LIMIT %s OFFSET %s
        """, tuple(params) + (t, (p - 1) * t))

    _bitacora("BITACORA_CONSULTADA", "EXITO", tipo="USUARIO")
    return responder(sobre_pagina([dict(f) for f in filas], total, p, t,
                                  clave="usuarios"), 200, raiz="usuarios_respuesta")


@app.get(f"{BASE}/<usuario_id>")
@requiere_permiso("USUARIO_ADMIN")
def detalle(usuario_id):
    limite_consumo()
    fila = consultar_uno(
        """
        SELECT u.usuario_id, u.nombre, u.apellido_paterno, u.apellido_materno,
               u.correo, u.activo, u.fecha_creacion, u.fecha_ultimo_acceso,
               up.perfil_id, pf.nombre AS perfil, up.unidad_alcance_id
          FROM usuarios.usuario u
          LEFT JOIN usuarios.usuario_perfil up USING (usuario_id)
          LEFT JOIN usuarios.perfil pf USING (perfil_id)
         WHERE u.usuario_id = %s
        """, (usuario_id,))
    if not fila:
        raise ErrorApi("USUARIO_NO_ENCONTRADO",
                       f"No existe el usuario {usuario_id}.", 404)
    permisos = consultar(
        "SELECT p.codigo, p.descripcion, p.sensible FROM usuarios.perfil_permiso pp "
        "JOIN usuarios.permiso p USING (permiso_id) WHERE pp.perfil_id = %s "
        "ORDER BY p.codigo", (fila["perfil_id"],))
    datos = dict(fila)
    datos["permisos"] = [dict(x) for x in permisos]
    return responder(datos, 200, raiz="usuario_respuesta")


# --------------------------------------------------------------- altas
@app.post(BASE)
@requiere_permiso("USUARIO_ADMIN")
def crear():
    limite_consumo(maximo=30)
    cuerpo = cuerpo_peticion()
    problemas = _validar_alta(cuerpo)
    if problemas:
        raise ErrorApi("VALIDACION", "La solicitud tiene campos invalidos.",
                       422, problemas)

    uid = cuerpo["usuario_id"].strip().upper()
    if consultar_uno("SELECT 1 AS x FROM usuarios.usuario WHERE usuario_id = %s", (uid,)):
        raise ErrorApi("USUARIO_DUPLICADO",
                       f"Ya existe un usuario con el identificador {uid}.", 409)
    if consultar_uno("SELECT 1 AS x FROM usuarios.usuario WHERE lower(correo) = lower(%s)",
                     (cuerpo["correo"],)):
        raise ErrorApi("CORREO_DUPLICADO",
                       "Ya hay un usuario con ese correo.", 409)
    if not consultar_uno("SELECT 1 AS x FROM usuarios.perfil WHERE perfil_id = %s",
                         (cuerpo["perfil_id"],)):
        raise ErrorApi("PERFIL_NO_EXISTE",
                       f"El perfil {cuerpo['perfil_id']} no existe.", 422)

    alcance = cuerpo.get("unidad_alcance_id") or None
    if alcance and not consultar_uno(
            "SELECT 1 AS x FROM organizacion.unidad_organizacional "
            "WHERE unidad_organizacional_id = %s AND activa", (alcance,)):
        raise ErrorApi("UNIDAD_NO_EXISTE",
                       f"La unidad {alcance} no existe o esta inactiva.", 422)

    # La contrasena se cifra en la base con crypt(): el texto plano no se
    # guarda en ningun momento y el hash nunca sale del motor.
    with cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO usuarios.usuario (usuario_id, nombre, apellido_paterno, "
            " apellido_materno, correo, contrasena_hash) "
            "VALUES (%s,%s,%s,%s,%s, crypt(%s, gen_salt('bf')))",
            (uid, cuerpo["nombre"].strip(), cuerpo["apellido_paterno"].strip(),
             (cuerpo.get("apellido_materno") or "").strip() or None,
             cuerpo["correo"].strip(), cuerpo["contrasena"]))
        cur.execute(
            "INSERT INTO usuarios.usuario_perfil (usuario_id, perfil_id, unidad_alcance_id) "
            "VALUES (%s,%s,%s)", (uid, cuerpo["perfil_id"], alcance))

    _bitacora("PERFIL_MODIFICADO", "EXITO", recurso=uid)
    return responder({"usuario_id": uid, "creado": True,
                      "mensaje": "Usuario creado y perfil asignado."},
                     201, raiz="usuario_creado")


@app.put(f"{BASE}/<usuario_id>/perfil")
@requiere_permiso("USUARIO_ADMIN")
def cambiar_perfil(usuario_id):
    limite_consumo(maximo=30)
    cuerpo = cuerpo_peticion()
    perfil_id = cuerpo.get("perfil_id")
    alcance = cuerpo.get("unidad_alcance_id") or None

    if not isinstance(perfil_id, int):
        raise ErrorApi("VALIDACION", "La solicitud tiene campos invalidos.", 422,
                       [{"campo": "perfil_id", "problema": "debe ser un entero"}])
    if not consultar_uno("SELECT 1 AS x FROM usuarios.usuario WHERE usuario_id = %s",
                         (usuario_id,)):
        raise ErrorApi("USUARIO_NO_ENCONTRADO", f"No existe {usuario_id}.", 404)
    if not consultar_uno("SELECT 1 AS x FROM usuarios.perfil WHERE perfil_id = %s",
                         (perfil_id,)):
        raise ErrorApi("PERFIL_NO_EXISTE", f"El perfil {perfil_id} no existe.", 422)

    with cursor(commit=True) as cur:
        cur.execute("DELETE FROM usuarios.usuario_perfil WHERE usuario_id = %s",
                    (usuario_id,))
        cur.execute("INSERT INTO usuarios.usuario_perfil "
                    "(usuario_id, perfil_id, unidad_alcance_id) VALUES (%s,%s,%s)",
                    (usuario_id, perfil_id, alcance))

    # Un cambio de perfil debe surtir efecto ya, no cuando caduque el token:
    # se revocan las sesiones vivas de ese usuario.
    revocadas = _revocar_sesiones(usuario_id)
    _bitacora("PERFIL_MODIFICADO", "EXITO", recurso=usuario_id)
    return responder({"usuario_id": usuario_id, "perfil_id": perfil_id,
                      "sesiones_revocadas": revocadas,
                      "mensaje": "Perfil actualizado; las sesiones activas se revocaron."},
                     200, raiz="perfil_actualizado")


@app.put(f"{BASE}/<usuario_id>/estado")
@requiere_permiso("USUARIO_ADMIN")
def cambiar_estado(usuario_id):
    limite_consumo(maximo=30)
    cuerpo = cuerpo_peticion()
    activo = cuerpo.get("activo")
    if not isinstance(activo, bool):
        raise ErrorApi("VALIDACION", "La solicitud tiene campos invalidos.", 422,
                       [{"campo": "activo", "problema": "debe ser true o false"}])
    if (g.actor or {}).get("sub") == usuario_id and not activo:
        # Desactivarse a si mismo deja al sistema potencialmente sin
        # administradores operativos. Se rechaza a proposito.
        raise ErrorApi("OPERACION_NO_PERMITIDA",
                       "Un administrador no puede desactivar su propia cuenta.", 409)

    with cursor(commit=True) as cur:
        cur.execute("UPDATE usuarios.usuario SET activo = %s, fecha_actualizacion = now() "
                    "WHERE usuario_id = %s RETURNING usuario_id", (activo, usuario_id))
        if not cur.fetchone():
            raise ErrorApi("USUARIO_NO_ENCONTRADO", f"No existe {usuario_id}.", 404)

    revocadas = 0 if activo else _revocar_sesiones(usuario_id)
    _bitacora("PERFIL_MODIFICADO", "EXITO", recurso=usuario_id)
    return responder({"usuario_id": usuario_id, "activo": activo,
                      "sesiones_revocadas": revocadas}, 200, raiz="estado_actualizado")


def _revocar_sesiones(usuario_id) -> int:
    """Revoca en Redis todas las sesiones vivas de un usuario."""
    try:
        r = obtener_redis()
        n = 0
        for clave in r.scan_iter("sesion:*", count=500):
            if r.hget(clave, "usuario_id") == usuario_id:
                jti = clave.split(":", 1)[1]
                r.setex(f"revocado:{jti}", 7 * 86400, "1")
                r.delete(clave)
                n += 1
        return n
    except Exception:
        app.logger.error("No se pudieron revocar las sesiones de %s", usuario_id)
        return 0


# ------------------------------------------------------ perfiles y permisos
@app.get(f"/api/{VERSION_API}/perfiles")
@requiere_token
def perfiles():
    limite_consumo()
    filas = consultar(
        """
        SELECT pf.perfil_id, pf.codigo, pf.nombre, pf.descripcion, pf.activo,
               count(pp.permiso_id) AS total_permisos,
               (SELECT count(*) FROM usuarios.usuario_perfil up
                 WHERE up.perfil_id = pf.perfil_id) AS usuarios_asignados
          FROM usuarios.perfil pf
          LEFT JOIN usuarios.perfil_permiso pp USING (perfil_id)
         GROUP BY pf.perfil_id, pf.codigo, pf.nombre, pf.descripcion, pf.activo
         ORDER BY pf.perfil_id
        """)
    return responder({"perfiles": [dict(f) for f in filas]},
                     200, raiz="perfiles_respuesta")


@app.get(f"/api/{VERSION_API}/perfiles/<int:perfil_id>/permisos")
@requiere_token
def permisos_de_perfil(perfil_id):
    limite_consumo()
    if not consultar_uno("SELECT 1 AS x FROM usuarios.perfil WHERE perfil_id = %s",
                         (perfil_id,)):
        raise ErrorApi("PERFIL_NO_EXISTE", f"El perfil {perfil_id} no existe.", 404)
    filas = consultar(
        "SELECT p.permiso_id, p.codigo, p.descripcion, p.sensible "
        "FROM usuarios.perfil_permiso pp JOIN usuarios.permiso p USING (permiso_id) "
        "WHERE pp.perfil_id = %s ORDER BY p.codigo", (perfil_id,))
    return responder({"perfil_id": perfil_id,
                      "permisos": [dict(f) for f in filas]},
                     200, raiz="permisos_respuesta")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PUERTO", "8102")))
