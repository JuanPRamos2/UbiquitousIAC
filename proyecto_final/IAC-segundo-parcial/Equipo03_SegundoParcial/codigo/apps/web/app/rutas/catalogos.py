"""
Catálogos operables: unidades organizacionales e instrumentos.

Son los dos catálogos que exige el entregable del primer parcial. La
operación sigue la regla de negocio RN-08: una unidad con colaboradores
activos no se elimina, se inactiva.
"""
from flask import (Blueprint, flash, redirect, render_template, request,
                   url_for)

from ..bitacora import registrar
from ..datos import consultar, consultar_uno, cursor
from ..seguridad import requiere_permiso

bp = Blueprint("catalogos", __name__, url_prefix="/catalogos")


# ------------------------------------------------------------- unidades
@bp.get("/unidades")
@requiere_permiso("INSTRUMENTO_ADMIN", "CAMPANIA_ADMIN", "USUARIO_ADMIN")
def unidades():
    filas = consultar(
        """
        SELECT u.unidad_organizacional_id, u.nombre, u.tipo, u.unidad_padre_id,
               u.nivel_jerarquico, u.plantilla_declarada, u.activa,
               (SELECT count(*) FROM usuarios.empleado e
                 WHERE e.unidad_organizacional_id = u.unidad_organizacional_id
                   AND e.activo) AS colaboradores
          FROM organizacion.unidad_organizacional u
         ORDER BY u.nivel_jerarquico, u.nombre
        """)
    return render_template("catalogos/unidades.html", filas=filas)


@bp.post("/unidades")
@requiere_permiso("USUARIO_ADMIN", "CAMPANIA_ADMIN")
def guardar_unidad():
    uid = (request.form.get("unidad_organizacional_id") or "").strip().upper()
    nombre = (request.form.get("nombre") or "").strip()
    tipo = request.form.get("tipo") or "TURNO"
    padre = request.form.get("unidad_padre_id") or None
    try:
        plantilla = int(request.form.get("plantilla_declarada") or 0)
    except ValueError:
        plantilla = 0

    if not uid or not nombre or plantilla <= 0:
        flash("Identificador, nombre y plantilla declarada son obligatorios.", "error")
        return redirect(url_for("catalogos.unidades"))

    nivel = 0
    if padre:
        p = consultar_uno("SELECT nivel_jerarquico FROM organizacion.unidad_organizacional "
                          "WHERE unidad_organizacional_id = %s", (padre,))
        if not p:
            flash("La unidad padre indicada no existe.", "error")
            return redirect(url_for("catalogos.unidades"))
        nivel = p["nivel_jerarquico"] + 1

    try:
        with cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO organizacion.unidad_organizacional
                    (unidad_organizacional_id, nombre, tipo, unidad_padre_id,
                     nivel_jerarquico, plantilla_declarada)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (unidad_organizacional_id) DO UPDATE
                    SET nombre = EXCLUDED.nombre,
                        tipo = EXCLUDED.tipo,
                        plantilla_declarada = EXCLUDED.plantilla_declarada,
                        fecha_actualizacion = now()
                """, (uid, nombre, tipo, padre, nivel, plantilla))
    except Exception as e:
        registrar("CATALOGO_MODIFICADO", "ERROR_TECNICO",
                  tipo_recurso="UNIDAD", recurso=uid)
        flash(f"No se pudo guardar la unidad: {e}", "error")
        return redirect(url_for("catalogos.unidades"))

    registrar("CATALOGO_MODIFICADO", "EXITO", tipo_recurso="UNIDAD", recurso=uid)
    flash(f"Unidad {uid} guardada.", "ok")
    return redirect(url_for("catalogos.unidades"))


@bp.post("/unidades/<uid>/inactivar")
@requiere_permiso("USUARIO_ADMIN", "CAMPANIA_ADMIN")
def inactivar_unidad(uid):
    """RN-08: no se elimina, se inactiva. Y solo si ya no tiene gente."""
    ocupada = consultar_uno(
        "SELECT count(*) AS n FROM usuarios.empleado "
        "WHERE unidad_organizacional_id = %s AND activo", (uid,))
    if ocupada and ocupada["n"] > 0:
        registrar("CATALOGO_MODIFICADO", "RECHAZADO",
                  tipo_recurso="UNIDAD", recurso=uid)
        flash(f"La unidad tiene {ocupada['n']} colaboradores activos. "
              f"Reasígnalos antes de inactivarla (RN-08).", "error")
        return redirect(url_for("catalogos.unidades"))

    with cursor(commit=True) as cur:
        cur.execute("UPDATE organizacion.unidad_organizacional "
                    "SET activa = FALSE, fecha_actualizacion = now() "
                    "WHERE unidad_organizacional_id = %s", (uid,))
    registrar("CATALOGO_MODIFICADO", "EXITO", tipo_recurso="UNIDAD", recurso=uid)
    flash(f"Unidad {uid} inactivada.", "ok")
    return redirect(url_for("catalogos.unidades"))


# --------------------------------------------------------- instrumentos
@bp.get("/instrumentos")
@requiere_permiso("INSTRUMENTO_ADMIN")
def instrumentos():
    filas = consultar(
        """
        SELECT i.instrumento_id, i.nombre, i.tipo, i.activo,
               f.nombre AS fuente, f.autorizada,
               (SELECT count(*) FROM catalogo.version_instrumento v
                 WHERE v.instrumento_id = i.instrumento_id) AS versiones
          FROM catalogo.instrumento i
          LEFT JOIN catalogo.fuente_autorizada f USING (fuente_id)
         ORDER BY i.nombre
        """)
    reactivos = consultar(
        "SELECT r.reactivo_id, r.texto, r.invertido, r.activo, d.nombre AS dimension "
        "FROM catalogo.reactivo r JOIN catalogo.dimension d USING (dimension_id) "
        "ORDER BY d.orden, r.reactivo_id")
    dimensiones = consultar("SELECT dimension_id, nombre FROM catalogo.dimension ORDER BY orden")
    return render_template("catalogos/instrumentos.html", filas=filas,
                           reactivos=reactivos, dimensiones=dimensiones)


@bp.post("/reactivos")
@requiere_permiso("INSTRUMENTO_ADMIN")
def guardar_reactivo():
    rid = (request.form.get("reactivo_id") or "").strip().upper()
    texto = (request.form.get("texto") or "").strip()
    dimension = request.form.get("dimension_id")
    invertido = request.form.get("invertido") == "1"

    if not rid or len(texto) < 10 or not dimension:
        flash("Identificador, texto (mínimo 10 caracteres) y dimensión son obligatorios.", "error")
        return redirect(url_for("catalogos.instrumentos"))

    try:
        with cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO catalogo.reactivo (reactivo_id, texto, dimension_id, invertido) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (reactivo_id) DO UPDATE SET texto = EXCLUDED.texto, "
                "  dimension_id = EXCLUDED.dimension_id, invertido = EXCLUDED.invertido",
                (rid, texto, dimension, invertido))
    except Exception as e:
        registrar("CATALOGO_MODIFICADO", "ERROR_TECNICO",
                  tipo_recurso="REACTIVO", recurso=rid)
        flash(f"No se pudo guardar el reactivo: {e}", "error")
        return redirect(url_for("catalogos.instrumentos"))

    registrar("CATALOGO_MODIFICADO", "EXITO", tipo_recurso="REACTIVO", recurso=rid)
    flash(f"Reactivo {rid} guardado.", "ok")
    return redirect(url_for("catalogos.instrumentos"))
