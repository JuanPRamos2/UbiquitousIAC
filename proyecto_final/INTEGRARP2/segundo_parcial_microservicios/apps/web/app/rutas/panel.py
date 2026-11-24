"""
Panel de resultados agregados.

Aquí está el punto donde el sistema decide qué puede mostrarse. La regla
importante: esta capa NO calcula el agregado. Llama a la función de la base
de datos, que aplica el umbral, el ruido de Laplace y el descuento de
presupuesto. Si esta capa intentara calcularlo por su cuenta, no podría:
el rol de base de datos de la aplicación no puede leer las respuestas.
"""
from flask import Blueprint, g, jsonify, render_template, request

from ..bitacora import registrar
from ..datos import consultar, consultar_uno, cursor
from ..seguridad import requiere_permiso

bp = Blueprint("panel", __name__, url_prefix="/panel")


def _unidades_visibles():
    """Un Líder de unidad solo ve la suya; los perfiles globales, todas.

    El filtro se aplica en la consulta, no escondiendo opciones en la
    pantalla: escribir otra unidad en la URL tampoco la muestra.
    """
    if "AGREGADO_GLOBAL" in g.permisos:
        return consultar(
            "SELECT unidad_organizacional_id, nombre, plantilla_declarada "
            "FROM organizacion.unidad_organizacional WHERE activa "
            "ORDER BY nivel_jerarquico, nombre")
    alcance = g.sesion.get("unidad_alcance")
    if not alcance:
        return []
    return consultar(
        "SELECT unidad_organizacional_id, nombre, plantilla_declarada "
        "FROM organizacion.unidad_organizacional "
        "WHERE activa AND unidad_organizacional_id = %s", (alcance,))


@bp.get("/")
@requiere_permiso("AGREGADO_UNIDAD", "AGREGADO_GLOBAL")
def inicio():
    unidades = _unidades_visibles()
    campanias = consultar(
        "SELECT campania_id, nombre, estado, secuencia FROM catalogo.campania "
        "ORDER BY secuencia DESC")
    unidad = request.args.get("unidad") or (
        unidades[0]["unidad_organizacional_id"] if unidades else None)
    # Por omision se muestra la ultima campania CERRADA, no la mas reciente:
    # mientras una campania sigue abierta esta recibiendo respuestas, y su
    # agregado cambiaria de una consulta a otra consumiendo presupuesto cada
    # vez. La abierta sigue disponible en el selector.
    cerradas = [c for c in campanias if c["estado"] == "CERRADA"]
    campania = request.args.get("campania") or (
        (cerradas or campanias)[0]["campania_id"] if campanias else None)

    # Que la unidad pedida esté entre las visibles se verifica aquí.
    permitidas = {u["unidad_organizacional_id"] for u in unidades}
    if unidad not in permitidas:
        unidad = next(iter(permitidas), None)

    resultado = presupuesto = None
    tablero = []
    reutilizado = False
    if unidad and campania:
        # Primero se busca un resultado YA publicado. Recalcularlo consumiria
        # presupuesto de epsilon otra vez, de modo que con solo recargar la
        # pagina se podria agotar el presupuesto de una unidad sin obtener
        # ninguna informacion nueva. El valor publicado es ademas el mismo que
        # vieron los demas: recalcular daria un numero distinto cada vez,
        # porque el ruido se sortea en cada calculo.
        publicado = consultar_uno(
            """
            SELECT estado_publicacion AS estado, n_observaciones AS n,
                   valor_protegido, epsilon_aplicado AS epsilon, escala_ruido,
                   'Valor protegido publicado el ' ||
                   to_char(fecha_calculo, 'DD/MM/YYYY HH24:MI') ||
                   '. Se reutiliza el resultado ya publicado en lugar de '
                   'recalcularlo, para no consumir presupuesto de privacidad.'
                   AS mensaje
              FROM agregado.resultado_protegido
             WHERE campania_id = %s AND unidad_organizacional_id = %s
               AND dimension_id IS NULL
             ORDER BY fecha_calculo DESC LIMIT 1
            """, (campania, unidad))

        if publicado:
            resultado = publicado
            reutilizado = True
        else:
            with cursor(commit=True) as cur:
                cur.execute(
                    "SELECT estado, n, valor_protegido, epsilon, escala_ruido, mensaje "
                    "FROM agregado.fn_calcular_agregado_protegido(%s, %s, NULL, %s)",
                    (campania, unidad, g.sesion["sub"]))
                resultado = cur.fetchone()

        estado = (resultado or {}).get("estado")
        registrar("AGREGADO_CONSULTADO",
                  "EXITO" if estado == "PUBLICADO" else
                  ("GRUPO_INSUFICIENTE" if estado and "UMBRAL" in estado
                   else "PRESUPUESTO_AGOTADO" if estado and "PRESUPUESTO" in estado
                   else "RECHAZADO"),
                  tipo_recurso="UNIDAD", recurso=unidad)

        presupuesto = consultar_uno(
            "SELECT * FROM agregado.v_estado_presupuesto "
            "WHERE campania_id = %s AND unidad_organizacional_id = %s",
            (campania, unidad))
        tablero = consultar(
            "SELECT * FROM agregado.v_tablero_unidad "
            "WHERE unidad_organizacional_id = %s AND campania_id = %s",
            (unidad, campania))

    return render_template("panel/inicio.html", unidades=unidades,
                           campanias=campanias, unidad=unidad,
                           campania=campania, resultado=resultado,
                           presupuesto=presupuesto, tablero=tablero,
                           reutilizado=reutilizado)


@bp.get("/tendencia.json")
@requiere_permiso("TENDENCIA_CONSULTAR", "AGREGADO_UNIDAD", "AGREGADO_GLOBAL")
def tendencia_json():
    """Serie para Highcharts. Solo devuelve valores ya publicados.

    No dispara cálculos nuevos, así que no consume presupuesto de privacidad:
    lee de la tabla de resultados ya protegidos.
    """
    unidad = request.args.get("unidad")
    permitidas = {u["unidad_organizacional_id"] for u in _unidades_visibles()}
    if unidad not in permitidas:
        return jsonify(error="Unidad fuera de tu alcance"), 403

    filas = consultar(
        "SELECT campania_nombre, secuencia, valor_protegido, n_observaciones, "
        "       escala_ruido, lectura "
        "FROM agregado.v_tendencia WHERE unidad_organizacional_id = %s "
        "  AND dimension_id IS NULL ORDER BY secuencia", (unidad,))
    registrar("TENDENCIA_CONSULTADA", "EXITO", tipo_recurso="UNIDAD", recurso=unidad)
    return jsonify(
        categorias=[f["campania_nombre"] for f in filas],
        valores=[float(f["valor_protegido"]) if f["valor_protegido"] is not None else None
                 for f in filas],
        n=[f["n_observaciones"] for f in filas],
        ruido=[float(f["escala_ruido"]) if f["escala_ruido"] is not None else None
               for f in filas],
    )


@bp.get("/recomendaciones")
@requiere_permiso("RECOMENDACION_CONSULTAR")
def recomendaciones():
    permitidas = {u["unidad_organizacional_id"] for u in _unidades_visibles()}
    if not permitidas:
        return render_template("panel/recomendaciones.html", filas=[])
    filas = consultar(
        "SELECT * FROM riesgo.v_recomendaciones "
        "WHERE unidad_organizacional_id = ANY(%s) ORDER BY nivel, orden",
        (list(permitidas),))
    return render_template("panel/recomendaciones.html", filas=filas)
