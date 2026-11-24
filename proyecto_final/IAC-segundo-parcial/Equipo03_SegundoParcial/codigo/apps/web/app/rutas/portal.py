"""
Portal del colaborador: consentimiento, encuesta y transparencia propia.

Este es el proceso principal de negocio del proyecto. Todo lo que ocurre
aquí se escribe contra el seudónimo de la persona, nunca contra su
identificador de empleado.
"""
import json

from flask import (Blueprint, abort, flash, g, redirect, render_template,
                   request, url_for)

from ..bitacora import registrar
from ..datos import consultar, consultar_uno, cursor
from ..seguridad import requiere_permiso, requiere_sesion

bp = Blueprint("portal", __name__, url_prefix="/portal")


def _seudonimo():
    """El seudónimo de quien tiene la sesión abierta.

    La aplicación nunca guarda esta correspondencia en la sesión ni en el
    token: se resuelve en cada petición contra la base, de modo que revocar
    un acceso surta efecto sin esperar a que caduque el token.
    """
    # Se resuelve por la vista del portal, no por la tabla de seudónimos.
    # El rol de la aplicación NO tiene permiso de lectura sobre esa tabla:
    # poder recorrer la correspondencia completa entre personas y seudónimos
    # sería exactamente lo que el proyecto promete que nadie puede hacer.
    # La vista del portal entrega una fila por usuario y nada más.
    f = consultar_uno(
        "SELECT seudonimo_id FROM portal.v_participacion_propia "
        "WHERE usuario_id = %s", (g.sesion["sub"],))
    return f["seudonimo_id"] if f else None


@bp.get("/")
@requiere_sesion
def inicio():
    if request.args.get("denegado"):
        flash("No tienes permiso para esa operación.", "error")

    datos = {}
    if "PARTICIPACION_PROPIA" in g.permisos:
        datos["participacion"] = consultar_uno(
            "SELECT * FROM portal.v_participacion_propia WHERE usuario_id = %s",
            (g.sesion["sub"],))
        datos["pendientes"] = consultar(
            "SELECT * FROM portal.v_campanias_pendientes WHERE usuario_id = %s "
            "ORDER BY fecha_inicio", (g.sesion["sub"],))
    return render_template("portal/inicio.html", **datos)


# ------------------------------------------------------- consentimiento
@bp.get("/consentimiento")
@requiere_permiso("CONSENT_OTORGAR", "CONSENT_HISTORIAL_PROPIO")
def consentimiento():
    seud = _seudonimo()
    aviso = consultar_uno(
        "SELECT * FROM consentimiento.aviso_privacidad WHERE vigente "
        "ORDER BY version DESC LIMIT 1")
    estado = consultar_uno(
        "SELECT estado, fecha_evento FROM consentimiento.v_estado_vigente "
        "WHERE seudonimo_id = %s", (seud,)) if seud else None
    historial = consultar(
        "SELECT estado, fecha_evento, aviso_id FROM consentimiento.consentimiento "
        "WHERE seudonimo_id = %s ORDER BY fecha_evento DESC", (seud,)) if seud else []
    return render_template("portal/consentimiento.html", aviso=aviso,
                           estado=estado, historial=historial)


@bp.post("/consentimiento")
@requiere_permiso("CONSENT_OTORGAR", "CONSENT_REVOCAR")
def cambiar_consentimiento():
    seud = _seudonimo()
    if not seud:
        abort(400)
    decision = request.form.get("decision")
    if decision not in ("ACEPTADO", "REVOCADO"):
        abort(400)

    aviso = consultar_uno("SELECT aviso_id FROM consentimiento.aviso_privacidad "
                          "WHERE vigente ORDER BY version DESC LIMIT 1")
    # Revocar NO borra el registro anterior: agrega un evento nuevo. Es la
    # decisión D-02, y es lo que permite acreditar qué se consintió y cuándo.
    with cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO consentimiento.consentimiento "
            "(seudonimo_id, aviso_id, estado) VALUES (%s, %s, %s)",
            (seud, aviso["aviso_id"], decision))

    registrar("CONSENT_OTORGADO" if decision == "ACEPTADO" else "CONSENT_REVOCADO",
              "EXITO", tipo_recurso="CONSENTIMIENTO", recurso=seud)
    flash("Consentimiento otorgado." if decision == "ACEPTADO"
          else "Consentimiento revocado. Tus respuestas anteriores se conservan, "
               "pero no se te pedirán nuevas respuestas.", "ok")
    return redirect(url_for("portal.consentimiento"))


# ---------------------------------------------------------------- encuesta
@bp.get("/encuesta/<campania_id>")
@requiere_permiso("AUTOREPORTE_RESPONDER")
def encuesta(campania_id):
    seud = _seudonimo()
    pendiente = consultar_uno(
        "SELECT * FROM portal.v_campanias_pendientes "
        "WHERE usuario_id = %s AND campania_id = %s",
        (g.sesion["sub"], campania_id))
    if not pendiente:
        flash("Esa campaña no está disponible para ti: puede estar cerrada, "
              "ya respondida, o tu consentimiento no está vigente.", "error")
        return redirect(url_for("portal.inicio"))

    reactivos = consultar(
        """
        SELECT r.reactivo_id, r.texto, r.invertido, d.nombre AS dimension, d.orden
          FROM catalogo.campania c
          JOIN catalogo.version_instrumento vi
            ON vi.instrumento_id = c.instrumento_id AND vi.version = c.version_instrumento
          JOIN catalogo.reactivo_version rv
            ON rv.instrumento_id = vi.instrumento_id AND rv.version = vi.version
          JOIN catalogo.reactivo r ON r.reactivo_id = rv.reactivo_id
          JOIN catalogo.dimension d ON d.dimension_id = r.dimension_id
         WHERE c.campania_id = %s AND r.activo
         ORDER BY d.orden, rv.orden
        """, (campania_id,))
    return render_template("portal/encuesta.html", campania=pendiente,
                           reactivos=reactivos, seudonimo=seud)


@bp.post("/encuesta/<campania_id>")
@requiere_permiso("AUTOREPORTE_RESPONDER")
def enviar_encuesta(campania_id):
    seud = _seudonimo()
    pendiente = consultar_uno(
        "SELECT * FROM portal.v_campanias_pendientes "
        "WHERE usuario_id = %s AND campania_id = %s",
        (g.sesion["sub"], campania_id))
    if not pendiente:
        registrar("AUTOREPORTE_ENVIADO", "RECHAZADO",
                  tipo_recurso="CAMPANIA", recurso=campania_id)
        flash("No se pudo registrar la respuesta: la campaña ya no admite envíos.", "error")
        return redirect(url_for("portal.inicio"))

    reactivos = consultar(
        """
        SELECT r.reactivo_id
          FROM catalogo.campania c
          JOIN catalogo.version_instrumento vi
            ON vi.instrumento_id = c.instrumento_id AND vi.version = c.version_instrumento
          JOIN catalogo.reactivo_version rv
            ON rv.instrumento_id = vi.instrumento_id AND rv.version = vi.version
          JOIN catalogo.reactivo r ON r.reactivo_id = rv.reactivo_id
         WHERE c.campania_id = %s AND r.activo
        """, (campania_id,))

    # Validación de entrada: cada reactivo debe traer un entero de 1 a 5.
    valores = {}
    for r in reactivos:
        crudo = request.form.get(f"r_{r['reactivo_id']}")
        try:
            v = int(crudo)
        except (TypeError, ValueError):
            flash("Faltan respuestas por contestar.", "error")
            return redirect(url_for("portal.encuesta", campania_id=campania_id))
        if not 1 <= v <= 5:
            abort(400)
        valores[r["reactivo_id"]] = v

    # La escritura la hace una función de la base de datos: la aplicación
    # no tiene permiso de uso sobre el esquema autoreporte. La función
    # vuelve a verificar campaña abierta, consentimiento vigente, RN-01 y
    # el rango de la escala, de modo que esas reglas valgan aunque un día
    # escriba otro cliente distinto de este.

    with cursor(commit=True) as cur:
        cur.execute(
            "SELECT estado, mensaje FROM autoreporte.fn_registrar_autoreporte(%s, %s, %s::jsonb)",
            (seud, campania_id, json.dumps(valores)))
        res = cur.fetchone()

    if not res or res["estado"] != "REGISTRADA":
        registrar("AUTOREPORTE_ENVIADO", "RECHAZADO",
                  tipo_recurso="CAMPANIA", recurso=campania_id)
        flash(f"No se registró la respuesta: {res['mensaje'] if res else 'error desconocido'}",
              "error")
        return redirect(url_for("portal.inicio"))

    registrar("AUTOREPORTE_ENVIADO", "EXITO", tipo_recurso="CAMPANIA",
              recurso=campania_id)
    flash("Gracias. Tu respuesta quedó registrada de forma seudonimizada: "
          "ni tu jefatura ni el área de bienestar pueden ver lo que contestaste.", "ok")
    return redirect(url_for("portal.inicio"))


# ---------------------------------------------------------- transparencia
@bp.get("/mis-accesos")
@requiere_permiso("PARTICIPACION_PROPIA")
def mis_accesos():
    """Quién tocó mis datos. Es la decisión D-08 hecha función."""
    accesos = consultar(
        "SELECT * FROM portal.v_accesos_a_mis_datos WHERE usuario_id = %s "
        "ORDER BY fecha_hora DESC LIMIT 100", (g.sesion["sub"],))
    return render_template("portal/mis_accesos.html", accesos=accesos)
