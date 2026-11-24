"""
M09 — Intervenciones organizacionales, y M10 — Evaluación.

Este módulo cierra el ciclo del proyecto. La regla que lo gobierna, y que
el modelo de datos hace cumplir, es que una intervención actúa sobre una
UNIDAD, nunca sobre una persona: no existe columna de empleado objetivo
en ninguna tabla del esquema intervencion, y la garantía G1 lo verifica.

El flujo es el que pide el objetivo del proyecto:

    resultado agregado protegido
      -> detección de condición (motor de reglas)
      -> recomendación
      -> el especialista propone un plan
      -> se aprueba
      -> se ejecuta y se registra seguimiento
      -> nueva campaña
      -> se compara la tendencia protegida
      -> se evalúa el efecto

La evaluación compara valores YA PUBLICADOS con ruido aplicado. Nunca
recalcula sobre las respuestas, de modo que medir el efecto de una
intervención no consume presupuesto de privacidad adicional ni abre una
vía para deducir respuestas individuales.
"""
from flask import (Blueprint, flash, g, redirect, render_template, request,
                   url_for)

from ..bitacora import registrar
from ..datos import consultar, consultar_uno, cursor
from ..seguridad import requiere_permiso

bp = Blueprint("intervenciones", __name__, url_prefix="/intervenciones")

# Transiciones permitidas del plan. Fuera de esto, el cambio se rechaza.
TRANSICIONES = {
    "PROPUESTA":    {"APROBADA", "CANCELADA"},
    "APROBADA":     {"EN_EJECUCION", "CANCELADA"},
    "EN_EJECUCION": {"FINALIZADA", "CANCELADA"},
    "FINALIZADA":   set(),
    "CANCELADA":    set(),
}

PERMISO_POR_ESTADO = {
    "APROBADA":     "INTERVENCION_APROBAR",
    "EN_EJECUCION": "INTERVENCION_SEGUIMIENTO",
    "FINALIZADA":   "INTERVENCION_SEGUIMIENTO",
    "CANCELADA":    "INTERVENCION_APROBAR",
}


@bp.get("/")
@requiere_permiso("INTERVENCION_PROPONER", "INTERVENCION_APROBAR",
                  "INTERVENCION_SEGUIMIENTO")
def listar():
    planes = consultar(
        """
        SELECT p.intervencion_id, p.unidad_organizacional_id, u.nombre AS unidad,
               t.nombre AS tipo, p.estado, p.fecha_inicio, p.fecha_fin,
               p.justificacion, p.resultado_esperado, p.campania_linea_base,
               p.responsable_usuario_id,
               (SELECT count(*) FROM intervencion.seguimiento s
                 WHERE s.intervencion_id = p.intervencion_id) AS seguimientos,
               (SELECT ev.conclusion FROM intervencion.evaluacion ev
                 WHERE ev.intervencion_id = p.intervencion_id) AS conclusion
          FROM intervencion.plan p
          JOIN organizacion.unidad_organizacional u
            ON u.unidad_organizacional_id = p.unidad_organizacional_id
          JOIN intervencion.tipo_intervencion t
            ON t.tipo_intervencion = p.tipo_intervencion
         ORDER BY p.intervencion_id DESC
        """)
    detecciones = consultar(
        "SELECT * FROM riesgo.v_recomendaciones ORDER BY nivel, orden LIMIT 40")
    tipos = consultar(
        "SELECT tipo_intervencion, nombre, descripcion "
        "FROM intervencion.tipo_intervencion ORDER BY nombre")
    campanias = consultar(
        "SELECT campania_id, nombre, secuencia FROM catalogo.campania "
        "ORDER BY secuencia DESC")
    # Se puede intervenir una unidad aunque el motor de reglas no haya
    # levantado una deteccion: el especialista puede tener informacion que
    # las reglas no capturan. Lo que no se puede es intervenir sin dejar
    # justificacion escrita.
    unidades = consultar(
        "SELECT unidad_organizacional_id, nombre FROM organizacion.unidad_organizacional "
        "WHERE activa ORDER BY nivel_jerarquico, nombre")
    return render_template("intervencion/lista.html", planes=planes,
                           detecciones=detecciones, tipos=tipos,
                           campanias=campanias, unidades=unidades)


@bp.post("/")
@requiere_permiso("INTERVENCION_PROPONER")
def proponer():
    unidad = request.form.get("unidad_organizacional_id")
    tipo = request.form.get("tipo_intervencion")
    justificacion = (request.form.get("justificacion") or "").strip()
    esperado = (request.form.get("resultado_esperado") or "").strip()
    inicio = request.form.get("fecha_inicio")
    fin = request.form.get("fecha_fin")
    linea_base = request.form.get("campania_linea_base") or None
    deteccion = request.form.get("deteccion_id") or None

    if not unidad or not tipo or len(justificacion) < 20 or not inicio or not fin:
        flash("Unidad, tipo, fechas y una justificación de al menos 20 caracteres "
              "son obligatorios. La justificación es lo que permite auditar "
              "después por qué se intervino.", "error")
        return redirect(url_for("intervenciones.listar"))
    if fin <= inicio:
        flash("La fecha de cierre debe ser posterior a la de inicio.", "error")
        return redirect(url_for("intervenciones.listar"))

    try:
        with cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO intervencion.plan
                    (unidad_organizacional_id, tipo_intervencion, deteccion_id,
                     justificacion, resultado_esperado, fecha_inicio, fecha_fin,
                     responsable_usuario_id, estado, campania_linea_base)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'PROPUESTA', %s)
                RETURNING intervencion_id
                """,
                (unidad, tipo, deteccion or None, justificacion, esperado,
                 inicio, fin, g.sesion["sub"], linea_base))
            nuevo = cur.fetchone()["intervencion_id"]
    except Exception as e:
        registrar("INTERVENCION_PROPUESTA", "ERROR_TECNICO",
                  tipo_recurso="UNIDAD", recurso=unidad)
        flash(f"No se pudo registrar el plan: {e}", "error")
        return redirect(url_for("intervenciones.listar"))

    registrar("INTERVENCION_PROPUESTA", "EXITO", tipo_recurso="UNIDAD", recurso=unidad)
    flash(f"Plan #{nuevo} propuesto para {unidad}. Queda en estado PROPUESTA "
          f"hasta que se apruebe.", "ok")
    return redirect(url_for("intervenciones.listar"))


@bp.post("/<int:plan_id>/estado")
def cambiar_estado(plan_id):
    nuevo = request.form.get("estado")
    permiso = PERMISO_POR_ESTADO.get(nuevo)
    if not permiso or permiso not in g.permisos:
        registrar("ACCESO_DENEGADO", "RECHAZADO",
                  tipo_recurso="INTERVENCION", recurso=str(plan_id))
        flash("No tienes permiso para ese cambio de estado.", "error")
        return redirect(url_for("intervenciones.listar"))

    plan = consultar_uno(
        "SELECT intervencion_id, estado, unidad_organizacional_id "
        "FROM intervencion.plan WHERE intervencion_id = %s", (plan_id,))
    if not plan:
        flash("El plan no existe.", "error")
        return redirect(url_for("intervenciones.listar"))

    if nuevo not in TRANSICIONES.get(plan["estado"], set()):
        registrar("INTERVENCION_APROBADA", "RECHAZADO",
                  tipo_recurso="INTERVENCION", recurso=str(plan_id))
        flash(f"No se puede pasar de {plan['estado']} a {nuevo}.", "error")
        return redirect(url_for("intervenciones.listar"))

    with cursor(commit=True) as cur:
        cur.execute("UPDATE intervencion.plan SET estado = %s "
                    "WHERE intervencion_id = %s", (nuevo, plan_id))

    registrar("INTERVENCION_APROBADA", "EXITO",
              tipo_recurso="INTERVENCION", recurso=str(plan_id))
    flash(f"Plan #{plan_id} ahora está en estado {nuevo}.", "ok")
    return redirect(url_for("intervenciones.listar"))


@bp.post("/<int:plan_id>/seguimiento")
@requiere_permiso("INTERVENCION_SEGUIMIENTO")
def seguimiento(plan_id):
    nota = (request.form.get("avance_nota") or "").strip()
    estado = request.form.get("estado_reportado") or "EN_EJECUCION"
    if len(nota) < 10:
        flash("La nota de avance necesita al menos 10 caracteres.", "error")
        return redirect(url_for("intervenciones.listar"))

    with cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO intervencion.seguimiento "
            "(intervencion_id, estado_reportado, avance_nota, registrado_por) "
            "VALUES (%s, %s, %s, %s)",
            (plan_id, estado, nota, g.sesion["sub"]))

    registrar("INTERVENCION_APROBADA", "EXITO",
              tipo_recurso="SEGUIMIENTO", recurso=str(plan_id))
    flash(f"Seguimiento registrado en el plan #{plan_id}.", "ok")
    return redirect(url_for("intervenciones.listar"))


# ---------------------------------------------------------------- M10
@bp.get("/<int:plan_id>/evaluar")
@requiere_permiso("INTERVENCION_SEGUIMIENTO")
def ver_evaluacion(plan_id):
    plan = consultar_uno(
        """
        SELECT p.*, u.nombre AS unidad, t.nombre AS tipo
          FROM intervencion.plan p
          JOIN organizacion.unidad_organizacional u
            ON u.unidad_organizacional_id = p.unidad_organizacional_id
          JOIN intervencion.tipo_intervencion t
            ON t.tipo_intervencion = p.tipo_intervencion
         WHERE p.intervencion_id = %s
        """, (plan_id,))
    if not plan:
        flash("El plan no existe.", "error")
        return redirect(url_for("intervenciones.listar"))

    # Solo campañas con resultado YA publicado para esa unidad. Evaluar no
    # dispara cálculos nuevos, así que no consume presupuesto.
    disponibles = consultar(
        """
        SELECT rp.campania_id, c.nombre, c.secuencia, rp.valor_protegido
          FROM agregado.resultado_protegido rp
          JOIN catalogo.campania c ON c.campania_id = rp.campania_id
         WHERE rp.unidad_organizacional_id = %s
           AND rp.dimension_id IS NULL
           AND rp.estado_publicacion = 'PUBLICADO'
         ORDER BY c.secuencia
        """, (plan["unidad_organizacional_id"],))

    evaluacion = consultar_uno(
        "SELECT * FROM intervencion.evaluacion WHERE intervencion_id = %s",
        (plan_id,))
    seguimientos = consultar(
        "SELECT * FROM intervencion.seguimiento WHERE intervencion_id = %s "
        "ORDER BY fecha_registro DESC", (plan_id,))
    return render_template("intervencion/evaluacion.html", plan=plan,
                           disponibles=disponibles, evaluacion=evaluacion,
                           seguimientos=seguimientos)


@bp.post("/<int:plan_id>/evaluar")
@requiere_permiso("INTERVENCION_SEGUIMIENTO")
def evaluar(plan_id):
    antes = request.form.get("campania_antes")
    despues = request.form.get("campania_despues")
    nota = (request.form.get("nota_metodologica") or "").strip()

    plan = consultar_uno(
        "SELECT unidad_organizacional_id, estado FROM intervencion.plan "
        "WHERE intervencion_id = %s", (plan_id,))
    if not plan:
        flash("El plan no existe.", "error")
        return redirect(url_for("intervenciones.listar"))
    if antes == despues:
        flash("Las campañas de antes y después deben ser distintas.", "error")
        return redirect(url_for("intervenciones.ver_evaluacion", plan_id=plan_id))

    valores = consultar(
        """
        SELECT rp.campania_id, rp.valor_protegido, rp.escala_ruido, c.secuencia
          FROM agregado.resultado_protegido rp
          JOIN catalogo.campania c ON c.campania_id = rp.campania_id
         WHERE rp.unidad_organizacional_id = %s
           AND rp.dimension_id IS NULL
           AND rp.estado_publicacion = 'PUBLICADO'
           AND rp.campania_id IN (%s, %s)
        """, (plan["unidad_organizacional_id"], antes, despues))
    por_id = {v["campania_id"]: v for v in valores}
    if antes not in por_id or despues not in por_id:
        flash("Alguna de las dos campañas no tiene resultado publicado para "
              "esta unidad. Sin resultado publicado no hay nada que comparar.", "error")
        return redirect(url_for("intervenciones.ver_evaluacion", plan_id=plan_id))

    v_antes = float(por_id[antes]["valor_protegido"])
    v_despues = float(por_id[despues]["valor_protegido"])
    variacion = round(v_despues - v_antes, 3)

    # El criterio de conclusión tiene que respetar el ruido: una diferencia
    # menor que el ruido de las dos mediciones no es un efecto, es azar.
    # Se suman las escalas de ruido de ambas campañas como banda mínima.
    ruido = (float(por_id[antes]["escala_ruido"] or 0)
             + float(por_id[despues]["escala_ruido"] or 0))
    banda = max(ruido, 0.05)

    if abs(variacion) <= banda:
        conclusion = "NO_CONCLUYENTE" if ruido > 0.2 else "SIN_CAMBIO"
    elif variacion > 0:
        conclusion = "MEJORA"
    else:
        conclusion = "DETERIORO"

    nota_completa = (
        f"Comparacion de valores protegidos ya publicados; no se recalculo sobre "
        f"respuestas ni se consumio presupuesto adicional. Banda de ruido combinada "
        f"{banda:.3f}; variacion observada {variacion:+.3f}. "
        + (nota or ""))

    with cursor(commit=True) as cur:
        cur.execute(
            """
            -- 'variacion' es una columna generada por la base de datos:
            -- se calcula sola a partir de los dos valores y no se inserta.
            -- Que la reste el motor evita que dos clientes distintos
            -- lleguen a numeros distintos para la misma evaluacion.
            INSERT INTO intervencion.evaluacion
                (intervencion_id, campania_antes, campania_despues,
                 valor_antes, valor_despues, conclusion, nota_metodologica)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (intervencion_id) DO UPDATE
               SET campania_antes = EXCLUDED.campania_antes,
                   campania_despues = EXCLUDED.campania_despues,
                   valor_antes = EXCLUDED.valor_antes,
                   valor_despues = EXCLUDED.valor_despues,
                   conclusion = EXCLUDED.conclusion,
                   nota_metodologica = EXCLUDED.nota_metodologica,
                   fecha_evaluacion = now()
            """, (plan_id, antes, despues, v_antes, v_despues,
                  conclusion, nota_completa))

    registrar("INTERVENCION_EVALUADA", "EXITO",
              tipo_recurso="INTERVENCION", recurso=str(plan_id))
    flash(f"Evaluación registrada: {conclusion} (variación {variacion:+.2f}).", "ok")
    return redirect(url_for("intervenciones.ver_evaluacion", plan_id=plan_id))
