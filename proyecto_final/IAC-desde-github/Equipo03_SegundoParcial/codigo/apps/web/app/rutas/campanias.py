"""
M04 — Campañas.

Una campaña es la ventana durante la cual se puede responder un
instrumento. Su ciclo es BORRADOR → ABIERTA → CERRADA, y cada paso tiene
consecuencias: abrir habilita respuestas, cerrar las detiene y deja la
campaña disponible para calcular agregados y tendencias.
"""
from flask import (Blueprint, flash, redirect, render_template, request,
                   url_for)

from ..bitacora import registrar
from ..datos import consultar, consultar_uno, cursor
from ..seguridad import requiere_permiso

bp = Blueprint("campanias", __name__, url_prefix="/campanias")

TRANSICIONES = {
    "BORRADOR": {"ABIERTA"},
    "ABIERTA": {"CERRADA"},
    "CERRADA": set(),          # una campaña cerrada no se reabre
}


@bp.get("/")
@requiere_permiso("CAMPANIA_ADMIN")
def listar():
    filas = consultar(
        """
        SELECT c.campania_id, c.nombre, c.estado, c.secuencia,
               c.fecha_inicio, c.fecha_fin, c.instrumento_id, c.version_instrumento,
               (SELECT count(*) FROM catalogo.campania_unidad cu
                 WHERE cu.campania_id = c.campania_id) AS unidades,
               (SELECT count(*) FROM agregado.resultado_protegido rp
                 WHERE rp.campania_id = c.campania_id) AS resultados
          FROM catalogo.campania c
         ORDER BY c.secuencia DESC
        """)
    instrumentos = consultar(
        "SELECT i.instrumento_id, i.nombre, v.version "
        "FROM catalogo.instrumento i "
        "JOIN catalogo.version_instrumento v USING (instrumento_id) "
        "WHERE i.activo AND v.activa ORDER BY i.nombre, v.version DESC")
    unidades = consultar(
        "SELECT unidad_organizacional_id, nombre, plantilla_declarada "
        "FROM organizacion.unidad_organizacional WHERE activa "
        "ORDER BY nivel_jerarquico, nombre")
    return render_template("catalogos/campanias.html", filas=filas,
                           instrumentos=instrumentos, unidades=unidades)


@bp.post("/")
@requiere_permiso("CAMPANIA_ADMIN")
def crear():
    cid = (request.form.get("campania_id") or "").strip().upper()
    nombre = (request.form.get("nombre") or "").strip()
    instrumento = request.form.get("instrumento") or ""
    inicio = request.form.get("fecha_inicio")
    fin = request.form.get("fecha_fin")
    unidades = request.form.getlist("unidades")

    if not cid or not nombre or not instrumento or not inicio or not fin:
        flash("Faltan datos obligatorios de la campaña.", "error")
        return redirect(url_for("campanias.listar"))
    if fin <= inicio:
        flash("La fecha de cierre debe ser posterior a la de apertura.", "error")
        return redirect(url_for("campanias.listar"))
    if not unidades:
        flash("Una campaña sin unidades participantes no se puede responder.", "error")
        return redirect(url_for("campanias.listar"))

    # El selector entrega "INSTRUMENTO|version".
    try:
        instrumento_id, version = instrumento.split("|")
        version = int(version)
    except ValueError:
        flash("Instrumento inválido.", "error")
        return redirect(url_for("campanias.listar"))

    siguiente = consultar_uno(
        "SELECT COALESCE(max(secuencia), 0) + 1 AS s FROM catalogo.campania")

    try:
        with cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO catalogo.campania
                    (campania_id, nombre, instrumento_id, version_instrumento,
                     fecha_inicio, fecha_fin, estado, secuencia)
                VALUES (%s, %s, %s, %s, %s, %s, 'BORRADOR', %s)
                """, (cid, nombre, instrumento_id, version, inicio, fin,
                      siguiente["s"]))
            for u in unidades:
                cur.execute(
                    "INSERT INTO catalogo.campania_unidad "
                    "(campania_id, unidad_organizacional_id) VALUES (%s, %s) "
                    "ON CONFLICT DO NOTHING", (cid, u))
    except Exception as e:
        registrar("CATALOGO_MODIFICADO", "ERROR_TECNICO",
                  tipo_recurso="CAMPANIA", recurso=cid)
        flash(f"No se pudo crear la campaña: {e}", "error")
        return redirect(url_for("campanias.listar"))

    registrar("CATALOGO_MODIFICADO", "EXITO", tipo_recurso="CAMPANIA", recurso=cid)
    flash(f"Campaña {cid} creada en borrador con {len(unidades)} unidades. "
          f"Ábrela cuando quieras empezar a recibir respuestas.", "ok")
    return redirect(url_for("campanias.listar"))


@bp.post("/<cid>/estado")
@requiere_permiso("CAMPANIA_ADMIN")
def cambiar_estado(cid):
    nuevo = request.form.get("estado")
    campania = consultar_uno(
        "SELECT campania_id, nombre, estado, instrumento_id, version_instrumento "
        "FROM catalogo.campania WHERE campania_id = %s", (cid,))
    if not campania:
        flash("La campaña no existe.", "error")
        return redirect(url_for("campanias.listar"))

    if nuevo not in TRANSICIONES.get(campania["estado"], set()):
        registrar("CATALOGO_MODIFICADO", "RECHAZADO",
                  tipo_recurso="CAMPANIA", recurso=cid)
        flash(f"No se puede pasar de {campania['estado']} a {nuevo}. "
              f"Una campaña cerrada no se reabre: hacerlo cambiaría agregados "
              f"ya publicados y el presupuesto de privacidad ya consumido.", "error")
        return redirect(url_for("campanias.listar"))

    if nuevo == "ABIERTA":
        # Dos campañas abiertas sobre el mismo instrumento confundirían a
        # quien responde y dividirían la participación.
        choque = consultar_uno(
            "SELECT campania_id FROM catalogo.campania "
            "WHERE estado = 'ABIERTA' AND instrumento_id = %s AND campania_id <> %s",
            (campania["instrumento_id"], cid))
        if choque:
            flash(f"La campaña {choque['campania_id']} ya está abierta sobre el "
                  f"mismo instrumento. Ciérrala primero.", "error")
            return redirect(url_for("campanias.listar"))
        if not consultar_uno("SELECT 1 AS x FROM catalogo.campania_unidad "
                             "WHERE campania_id = %s LIMIT 1", (cid,)):
            flash("La campaña no tiene unidades participantes.", "error")
            return redirect(url_for("campanias.listar"))

    with cursor(commit=True) as cur:
        cur.execute("UPDATE catalogo.campania SET estado = %s WHERE campania_id = %s",
                    (nuevo, cid))

    registrar("CATALOGO_MODIFICADO", "EXITO", tipo_recurso="CAMPANIA", recurso=cid)
    if nuevo == "ABIERTA":
        flash(f"Campaña {cid} abierta. Las personas con consentimiento vigente "
              f"en las unidades participantes ya pueden responder.", "ok")
    else:
        flash(f"Campaña {cid} cerrada. Ya se pueden calcular sus agregados "
              f"protegidos y compararlos con campañas anteriores.", "ok")
    return redirect(url_for("campanias.listar"))
