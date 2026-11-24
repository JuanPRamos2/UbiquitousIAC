"""
Administración de usuarios, perfiles y permisos en el sistema web.

Es la parte de interfaz del Integrante 1. Las pantallas llaman a
users-service cuando está disponible, y caen a la base de datos cuando no:
el sistema web debe seguir funcionando de manera independiente, que es un
requisito explícito de la arquitectura obligatoria.

Esa caída no es un parche: está escrita a propósito y la pantalla dice al
operador por cuál de las dos vías obtuvo los datos, para que durante la
demostración se pueda apagar el microservicio y ver que el portal aguanta.
"""
import os

import requests
from flask import (Blueprint, current_app, flash, g, redirect, render_template,
                   request, url_for)

from ..bitacora import registrar
from ..datos import consultar, consultar_uno, cursor
from ..seguridad import COOKIE, requiere_permiso

bp = Blueprint("administracion", __name__, url_prefix="/administracion")

USERS_SERVICE = os.environ.get("USERS_SERVICE_URL", "")
TIEMPO_LIMITE = float(os.environ.get("MICROSERVICIO_TIMEOUT", "2.5"))


def _llamar_microservicio(ruta, metodo="GET", json_cuerpo=None):
    """Devuelve (datos, origen) u (None, 'base de datos') si no se pudo.

    Nunca lanza: si el microservicio no responde, la pantalla sigue.
    """
    if not USERS_SERVICE:
        return None, "base de datos"
    try:
        token = request.cookies.get(COOKIE, "")
        r = requests.request(
            metodo, f"{USERS_SERVICE}{ruta}", json=json_cuerpo,
            headers={"Authorization": f"Bearer {token}",
                     "X-Correlacion-Id": getattr(g, "correlacion_id", "")},
            timeout=TIEMPO_LIMITE)
        if r.status_code >= 500:
            return None, "base de datos"
        return (r.json(), "users-service")
    except Exception as e:
        current_app.logger.warning("users-service no respondio (%s); se usa la base", e)
        return None, "base de datos"


@bp.get("/usuarios")
@requiere_permiso("USUARIO_ADMIN")
def usuarios():
    busqueda = (request.args.get("busqueda") or "").strip()
    perfil = request.args.get("perfil_id") or ""
    try:
        pagina = max(1, int(request.args.get("pagina", 1)))
    except ValueError:
        pagina = 1
    tamano = 15

    consulta = f"?pagina={pagina}&tamano={tamano}"
    if busqueda:
        consulta += f"&busqueda={busqueda}"
    if perfil:
        consulta += f"&perfil_id={perfil}"

    datos, origen = _llamar_microservicio(f"/api/v1/usuarios{consulta}")

    if datos and "usuarios" in datos:
        filas = datos["usuarios"]
        paginacion = datos["paginacion"]
    else:
        # Camino autónomo: la misma consulta contra PostgreSQL.
        filtros, params = ["1=1"], []
        if busqueda:
            filtros.append("(u.nombre ILIKE %s OR u.apellido_paterno ILIKE %s "
                           "OR u.correo ILIKE %s OR u.usuario_id ILIKE %s)")
            params += [f"%{busqueda}%"] * 4
        if perfil.isdigit():
            filtros.append("up.perfil_id = %s")
            params.append(int(perfil))
        donde = " AND ".join(filtros)
        total = consultar_uno(
            f"SELECT count(*) AS n FROM usuarios.usuario u "
            f"LEFT JOIN usuarios.usuario_perfil up USING (usuario_id) WHERE {donde}",
            tuple(params))["n"]
        filas = consultar(
            f"""SELECT u.usuario_id, u.nombre, u.apellido_paterno, u.correo,
                       u.activo, u.fecha_ultimo_acceso, up.perfil_id,
                       pf.nombre AS perfil, up.unidad_alcance_id
                  FROM usuarios.usuario u
                  LEFT JOIN usuarios.usuario_perfil up USING (usuario_id)
                  LEFT JOIN usuarios.perfil pf USING (perfil_id)
                 WHERE {donde} ORDER BY u.usuario_id LIMIT %s OFFSET %s""",
            tuple(params) + (tamano, (pagina - 1) * tamano))
        total_paginas = max(1, (total + tamano - 1) // tamano)
        paginacion = {"pagina": pagina, "tamano": tamano, "total": total,
                      "total_paginas": total_paginas,
                      "tiene_siguiente": pagina < total_paginas,
                      "tiene_anterior": pagina > 1}

    perfiles = consultar("SELECT perfil_id, nombre FROM usuarios.perfil ORDER BY perfil_id")
    unidades = consultar("SELECT unidad_organizacional_id, nombre "
                         "FROM organizacion.unidad_organizacional WHERE activa "
                         "ORDER BY nivel_jerarquico, nombre")
    return render_template("admin/usuarios.html", filas=filas, paginacion=paginacion,
                           perfiles=perfiles, unidades=unidades, origen=origen,
                           busqueda=busqueda, perfil_filtro=perfil)


@bp.post("/usuarios")
@requiere_permiso("USUARIO_ADMIN")
def crear_usuario():
    cuerpo = {
        "usuario_id": (request.form.get("usuario_id") or "").strip().upper(),
        "nombre": (request.form.get("nombre") or "").strip(),
        "apellido_paterno": (request.form.get("apellido_paterno") or "").strip(),
        "apellido_materno": (request.form.get("apellido_materno") or "").strip(),
        "correo": (request.form.get("correo") or "").strip(),
        "contrasena": request.form.get("contrasena") or "",
        "perfil_id": int(request.form.get("perfil_id") or 0) or None,
        "unidad_alcance_id": request.form.get("unidad_alcance_id") or None,
    }

    datos, origen = _llamar_microservicio("/api/v1/usuarios", "POST", cuerpo)
    if datos is not None:
        if "error" in datos:
            detalles = datos["error"].get("detalles") or []
            texto = "; ".join(f"{d['campo']}: {d['problema']}" for d in detalles)
            flash(f"{datos['error']['mensaje']} {texto}".strip(), "error")
        else:
            flash(f"Usuario {cuerpo['usuario_id']} creado mediante users-service.", "ok")
        return redirect(url_for("administracion.usuarios"))

    # Camino autónomo. Se repiten las validaciones: el sistema web no puede
    # confiar en que el microservicio haya validado si no lo llamó.
    problemas = []
    import re
    if not re.match(r"^USR-\d{5}$", cuerpo["usuario_id"]):
        problemas.append("el identificador debe tener la forma USR-00000")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$", cuerpo["correo"]):
        problemas.append("el correo no es valido")
    if len(cuerpo["nombre"]) < 2 or len(cuerpo["apellido_paterno"]) < 2:
        problemas.append("nombre y apellido requieren al menos 2 caracteres")
    if len(cuerpo["contrasena"]) < 8:
        problemas.append("la contrasena requiere al menos 8 caracteres")
    if not cuerpo["perfil_id"]:
        problemas.append("falta el perfil")
    if problemas:
        flash("No se pudo crear: " + "; ".join(problemas) + ".", "error")
        return redirect(url_for("administracion.usuarios"))

    if consultar_uno("SELECT 1 AS x FROM usuarios.usuario WHERE usuario_id = %s "
                     "OR lower(correo) = lower(%s)",
                     (cuerpo["usuario_id"], cuerpo["correo"])):
        flash("Ya existe un usuario con ese identificador o ese correo.", "error")
        return redirect(url_for("administracion.usuarios"))

    try:
        with cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO usuarios.usuario (usuario_id, nombre, apellido_paterno, "
                " apellido_materno, correo, contrasena_hash) "
                "VALUES (%s,%s,%s,%s,%s, crypt(%s, gen_salt('bf')))",
                (cuerpo["usuario_id"], cuerpo["nombre"], cuerpo["apellido_paterno"],
                 cuerpo["apellido_materno"] or None, cuerpo["correo"],
                 cuerpo["contrasena"]))
            cur.execute("INSERT INTO usuarios.usuario_perfil "
                        "(usuario_id, perfil_id, unidad_alcance_id) VALUES (%s,%s,%s)",
                        (cuerpo["usuario_id"], cuerpo["perfil_id"],
                         cuerpo["unidad_alcance_id"]))
    except Exception as e:
        registrar("PERFIL_MODIFICADO", "ERROR_TECNICO",
                  tipo_recurso="USUARIO", recurso=cuerpo["usuario_id"])
        flash(f"No se pudo crear el usuario: {e}", "error")
        return redirect(url_for("administracion.usuarios"))

    registrar("PERFIL_MODIFICADO", "EXITO", tipo_recurso="USUARIO",
              recurso=cuerpo["usuario_id"])
    flash(f"Usuario {cuerpo['usuario_id']} creado (sin microservicio).", "ok")
    return redirect(url_for("administracion.usuarios"))


@bp.post("/usuarios/<usuario_id>/perfil")
@requiere_permiso("USUARIO_ADMIN")
def cambiar_perfil(usuario_id):
    try:
        perfil_id = int(request.form.get("perfil_id") or 0)
    except ValueError:
        perfil_id = 0
    alcance = request.form.get("unidad_alcance_id") or None
    if not perfil_id:
        flash("Perfil invalido.", "error")
        return redirect(url_for("administracion.usuarios"))

    datos, origen = _llamar_microservicio(
        f"/api/v1/usuarios/{usuario_id}/perfil", "PUT",
        {"perfil_id": perfil_id, "unidad_alcance_id": alcance})

    if datos is not None and "error" not in datos:
        flash(f"Perfil actualizado mediante users-service. "
              f"Sesiones revocadas: {datos.get('sesiones_revocadas', 0)}.", "ok")
        return redirect(url_for("administracion.usuarios"))

    with cursor(commit=True) as cur:
        cur.execute("DELETE FROM usuarios.usuario_perfil WHERE usuario_id = %s",
                    (usuario_id,))
        cur.execute("INSERT INTO usuarios.usuario_perfil "
                    "(usuario_id, perfil_id, unidad_alcance_id) VALUES (%s,%s,%s)",
                    (usuario_id, perfil_id, alcance))
    registrar("PERFIL_MODIFICADO", "EXITO", tipo_recurso="USUARIO", recurso=usuario_id)
    flash(f"Perfil de {usuario_id} actualizado.", "ok")
    return redirect(url_for("administracion.usuarios"))


@bp.post("/usuarios/<usuario_id>/estado")
@requiere_permiso("USUARIO_ADMIN")
def cambiar_estado(usuario_id):
    activo = request.form.get("activo") == "1"
    if usuario_id == g.sesion["sub"] and not activo:
        flash("No puedes desactivar tu propia cuenta: dejaria al sistema "
              "potencialmente sin administradores operativos.", "error")
        return redirect(url_for("administracion.usuarios"))

    datos, origen = _llamar_microservicio(
        f"/api/v1/usuarios/{usuario_id}/estado", "PUT", {"activo": activo})
    if datos is not None and "error" not in datos:
        flash(f"Estado actualizado mediante users-service.", "ok")
        return redirect(url_for("administracion.usuarios"))

    with cursor(commit=True) as cur:
        cur.execute("UPDATE usuarios.usuario SET activo = %s, "
                    "fecha_actualizacion = now() WHERE usuario_id = %s",
                    (activo, usuario_id))
    registrar("PERFIL_MODIFICADO", "EXITO", tipo_recurso="USUARIO", recurso=usuario_id)
    flash(f"Usuario {usuario_id} {'activado' if activo else 'desactivado'}.", "ok")
    return redirect(url_for("administracion.usuarios"))


@bp.get("/permisos")
@requiere_permiso("USUARIO_ADMIN", "BITACORA_CONSULTAR")
def permisos():
    """Matriz de perfiles contra permisos, calculada desde la base.

    Es la misma matriz del documento de actores, pero viva: si alguien
    cambia un permiso, esta pantalla lo muestra sin que nadie actualice
    un documento.
    """
    perfiles = consultar("SELECT perfil_id, codigo, nombre FROM usuarios.perfil "
                         "ORDER BY perfil_id")
    permisos_lista = consultar("SELECT permiso_id, codigo, descripcion, sensible "
                               "FROM usuarios.permiso ORDER BY permiso_id")
    asignados = consultar("SELECT perfil_id, permiso_id FROM usuarios.perfil_permiso")
    matriz = {(a["perfil_id"], a["permiso_id"]) for a in asignados}
    return render_template("admin/permisos.html", perfiles=perfiles,
                           permisos=permisos_lista, matriz=matriz)


@bp.get("/servicios")
@requiere_permiso("PARAMETRO_ADMIN", "USUARIO_ADMIN")
def servicios():
    """Monitoreo de los microservicios: disponible, degradado o caído.

    Consulta el endpoint de salud de cada uno. Es lo que permite demostrar
    que el sistema web sigue operando con los microservicios apagados.
    """
    catalogo = [
        ("auth-service", os.environ.get("AUTH_SERVICE_URL", "http://auth-service:8000")),
        ("users-service", os.environ.get("USERS_SERVICE_URL", "http://users-service:8000")),
        ("documents-service", os.environ.get("DOCUMENTS_SERVICE_URL",
                                             "http://documents-service:8000")),
        ("notifications-service", os.environ.get("NOTIFICATIONS_SERVICE_URL",
                                                 "http://notifications-service:8000")),
    ]
    import time
    filas = []
    for nombre, url in catalogo:
        inicio = time.perf_counter()
        estado, detalle, dependencias = "CAIDO", "", {}
        try:
            r = requests.get(f"{url}/health/ready", timeout=TIEMPO_LIMITE)
            cuerpo = r.json()
            dependencias = cuerpo.get("dependencias", {})
            estado = "DISPONIBLE" if r.status_code == 200 else "DEGRADADO"
            detalle = cuerpo.get("estado", "")
        except Exception as e:
            detalle = str(e)[:120]
        filas.append({
            "servicio": nombre, "url": url, "estado": estado, "detalle": detalle,
            "ms": round((time.perf_counter() - inicio) * 1000, 1),
            "dependencias": dependencias,
        })
    return render_template("admin/servicios.html", filas=filas)
