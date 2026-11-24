"""
Bitácora de auditoría, verificación de garantías y parámetros de privacidad.

Estas pantallas son de control, no de operación. Están juntas porque
comparten una propiedad: quien las usa vigila al sistema, y el sistema
registra también esa vigilancia.
"""
from flask import (Blueprint, flash, redirect, render_template, request,
                   url_for)

from ..bitacora import registrar
from ..datos import consultar, consultar_uno, cursor
from ..seguridad import requiere_permiso

bp = Blueprint("gobierno", __name__, url_prefix="/gobierno")


@bp.get("/bitacora")
@requiere_permiso("BITACORA_CONSULTAR")
def bitacora():
    accion = request.args.get("accion") or None
    resultado = request.args.get("resultado") or None
    filas = consultar(
        """
        SELECT b.fecha_hora, b.actor_usuario_id, b.actor_perfil,
               ta.descripcion AS accion, b.accion AS accion_codigo,
               b.tipo_recurso, b.recurso_id,
               re.descripcion AS resultado, b.resultado AS resultado_codigo,
               b.correlacion_id
          FROM auditoria.bitacora b
          JOIN auditoria.tipo_accion ta ON ta.codigo = b.accion
          JOIN auditoria.resultado   re ON re.codigo = b.resultado
         WHERE (%s IS NULL OR b.accion = %s)
           AND (%s IS NULL OR b.resultado = %s)
         ORDER BY b.bitacora_id DESC
         LIMIT 200
        """, (accion, accion, resultado, resultado))
    acciones = consultar("SELECT codigo, descripcion FROM auditoria.tipo_accion ORDER BY codigo")
    resultados = consultar("SELECT codigo, descripcion FROM auditoria.resultado ORDER BY codigo")

    # Consultar la bitácora es en sí una acción auditable.
    registrar("BITACORA_CONSULTADA", "EXITO", tipo_recurso="BITACORA")
    return render_template("auditoria/bitacora.html", filas=filas,
                           acciones=acciones, resultados=resultados,
                           f_accion=accion, f_resultado=resultado)


@bp.get("/garantias")
@requiere_permiso("BITACORA_CONSULTAR", "PARAMETRO_ADMIN")
def garantias():
    """Las seis garantías del proyecto, verificadas contra la base en vivo.

    No es una lista escrita a mano: cada renglón lo calcula una función que
    consulta el catálogo del motor. Si alguien agregara una columna que
    rompe una garantía, este tablero lo mostraría.
    """
    filas = consultar("SELECT * FROM gobernanza.fn_verificar_garantias()")
    return render_template("auditoria/garantias.html", filas=filas)


@bp.get("/parametros")
@requiere_permiso("PARAMETRO_ADMIN")
def parametros():
    params = consultar(
        "SELECT clave, valor, descripcion FROM agregado.parametro_privacidad ORDER BY clave")
    presupuestos = consultar(
        "SELECT * FROM agregado.v_estado_presupuesto ORDER BY campania_id, unidad")
    return render_template("admin/parametros.html", params=params,
                           presupuestos=presupuestos)


@bp.post("/parametros")
@requiere_permiso("PARAMETRO_ADMIN")
def guardar_parametro():
    clave = request.form.get("clave")
    valor = request.form.get("valor")
    actual = consultar_uno(
        "SELECT clave FROM agregado.parametro_privacidad WHERE clave = %s", (clave,))
    if not actual:
        flash("Parámetro desconocido.", "error")
        return redirect(url_for("gobierno.parametros"))
    try:
        v = float(valor)
    except (TypeError, ValueError):
        flash("El valor debe ser numérico.", "error")
        return redirect(url_for("gobierno.parametros"))

    # Rangos defendibles. Un k menor a 5 o un épsilon mayor a 2 dejarían
    # de proteger de forma significativa, y el sistema no debe permitir
    # que un descuido los deje así.
    limites = {"k_umbral_minimo": (5, 50), "epsilon_por_consulta": (0.1, 2.0),
               "presupuesto_campania": (1.0, 20.0), "error_tolerado": (0.05, 1.0),
               "n_minimo_utilidad": (5, 100)}
    if clave in limites:
        lo, hi = limites[clave]
        if not lo <= v <= hi:
            registrar("PARAMETRO_MODIFICADO", "RECHAZADO",
                      tipo_recurso="PARAMETRO", recurso=clave)
            flash(f"El valor de {clave} debe estar entre {lo} y {hi}.", "error")
            return redirect(url_for("gobierno.parametros"))

    with cursor(commit=True) as cur:
        cur.execute("UPDATE agregado.parametro_privacidad SET valor = %s "
                    "WHERE clave = %s", (v, clave))
    registrar("PARAMETRO_MODIFICADO", "EXITO", tipo_recurso="PARAMETRO", recurso=clave)
    flash(f"Parámetro {clave} actualizado a {v}. El cambio quedó en la bitácora.", "ok")
    return redirect(url_for("gobierno.parametros"))


@bp.get("/consentimientos")
@requiere_permiso("CONSENT_EVIDENCIA_AUDIT")
def consentimientos():
    """Evidencia de consentimiento SIN contenido de respuestas.

    El auditor ve que existe consentimiento vigente y de qué versión del
    aviso, nunca qué contestó la persona. Es la distinción que sostiene
    la garantía G2.
    """
    filas = consultar(
        """
        SELECT ev.seudonimo_id, ev.estado, ev.fecha_evento, c.aviso_id
          FROM consentimiento.v_estado_vigente ev
          JOIN consentimiento.consentimiento c
            ON c.seudonimo_id = ev.seudonimo_id AND c.fecha_evento = ev.fecha_evento
         ORDER BY ev.fecha_evento DESC
         LIMIT 100
        """)
    resumen = consultar(
        "SELECT estado, count(*) AS n FROM consentimiento.v_estado_vigente "
        "GROUP BY estado ORDER BY estado")
    registrar("CONSENT_VERIFICADO", "EXITO", tipo_recurso="CONSENTIMIENTO")
    return render_template("auditoria/consentimientos.html", filas=filas, resumen=resumen)
