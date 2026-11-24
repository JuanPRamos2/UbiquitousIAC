"""
trends-service — análisis longitudinal de indicadores agregados.

QUÉ RESPONDE ESTE SERVICIO, Y POR QUÉ NO LO RESPONDE OTRO
----------------------------------------------------------
La pregunta es una sola: **¿este cambio entre campañas es real, o cabe
dentro del ruido?**

Parece una pregunta menor y es la más importante que se le puede hacer a
esta plataforma. Todos los valores publicados llevan ruido de Laplace. Si
una unidad pasó de 3.4 a 3.2, esa caída de 0.2 puede ser una señal
verdadera o puede ser enteramente azar, según cuánto ruido se le aplicó. Un
tablero que dibuje las dos situaciones igual lleva a intervenir sobre una
unidad en la que no pasó nada, y a no intervenir en una en la que sí.

Ningún otro componente contesta eso:

  · queries-service lee la serie y la devuelve tal cual. No interpreta.
  · algorithms-service evalúa reglas sobre UNA campaña: dice «esta unidad
    está por debajo del umbral hoy», no «esta unidad viene cayendo».
  · reports-service compara dos reportes puntuales.

Este servicio toma la serie completa de una unidad y dimensión y decide,
punto por punto, si el movimiento supera el ruido.

LA REGLA DE DECISIÓN, Y POR QUÉ ESTA
-------------------------------------
Dos valores con ruido de Laplace de escala b cada uno. La diferencia de los
dos tiene una dispersión del orden de b·√2. Se exige que la diferencia
absoluta la supere para llamarla cambio real.

No es una prueba de hipótesis formal y no se presenta como tal: sería
pretender una precisión que estos datos no tienen, porque el ruido se
aplicó por separado a cada punto y las muestras no son independientes
entre campañas (en buena medida son las mismas personas). Es un criterio
conservador y explicable, que es lo que sirve para decidir si vale la pena
mirar una unidad.

LO QUE NO HACE, A PROPÓSITO
---------------------------
No extrapola. No dice «si sigue así, en tres campañas estará en 2.1».
Proyectar sobre valores con ruido produce una línea que se ve científica y
no tiene sustento, y alguien la usaría para justificar una decisión sobre
gente real.

No consume presupuesto de épsilon: lee resultados YA PUBLICADOS, igual que
queries-service. Por eso `epsilon_consumido` sale en cero en cada
respuesta, y es obligatorio: el día que deje de ser cero, se nota.
"""
import datetime as dt
import math
import os

from flask import g, request

from comun import (ErrorApi, VERSION_API, crear_servicio, cuerpo_peticion,
                   limite_consumo, obtener_redis, pagina, responder,
                   requiere_permiso, sobre_pagina)
from comun.datos import consultar, consultar_uno, cursor, ping as ping_pg

os.environ.setdefault("NOMBRE_SERVICIO", "trends-service")

# Mínimo de puntos para hablar de tendencia. Con dos puntos hay una
# diferencia, no una tendencia, y llamarla tendencia invita a leer una
# dirección donde solo hay un salto.
MINIMO_PUNTOS = 3

# Multiplicador sobre la escala del ruido. √2 porque se restan dos valores
# que llevan ruido independiente de la misma escala.
FACTOR_RUIDO = math.sqrt(2)


def _ping_redis():
    obtener_redis().ping()


app = crear_servicio(
    "trends-service",
    "Analisis longitudinal de indicadores agregados, con control de ruido",
    comprobaciones={"postgresql": ping_pg, "redis": _ping_redis})

from contrato import montar as _montar_contrato  # noqa: E402
_montar_contrato(app)

BASE = f"/api/{VERSION_API}/tendencias"


def _bitacora(accion, resultado, recurso=None):
    try:
        with cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO auditoria.bitacora (actor_usuario_id, actor_perfil, "
                " accion, tipo_recurso, recurso_id, resultado, correlacion_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                ((g.get("actor") or {}).get("sub"),
                 ((g.get("actor") or {}).get("perfil") or "ANONIMO")[:30],
                 accion, "CONSULTA", recurso, resultado,
                 getattr(g, "correlacion_id", "")))
    except Exception:
        app.logger.error("No se pudo escribir en la bitacora: %s", accion)


def _alcance_permite(unidad_id):
    """El alcance sale del perfil asignado, nunca del parámetro.

    Si se tomara del parámetro bastaría cambiar la URL para ver la serie
    de otra área.
    """
    actor = g.get("actor") or {}
    alcance = actor.get("unidad_alcance")
    if not alcance:
        return True
    if alcance == unidad_id:
        return True
    fila = consultar_uno(
        "WITH RECURSIVE arbol AS ("
        "  SELECT unidad_organizacional_id FROM organizacion.unidad_organizacional"
        "   WHERE unidad_organizacional_id = %s"
        "  UNION ALL"
        "  SELECT u.unidad_organizacional_id"
        "    FROM organizacion.unidad_organizacional u"
        "    JOIN arbol a ON u.unidad_padre_id = a.unidad_organizacional_id)"
        " SELECT 1 AS x FROM arbol WHERE unidad_organizacional_id = %s",
        (alcance, unidad_id))
    return bool(fila)


def _flotante(valor):
    return None if valor is None else float(valor)


def _serie(unidad_id, dimension_id=None):
    sql = ("SELECT unidad_organizacional_id, unidad_nombre, dimension_id, "
           "       secuencia, campania_id, campania_nombre, valor_protegido, "
           "       n_observaciones, escala_ruido, variacion_absoluta, lectura "
           "  FROM agregado.v_tendencia "
           " WHERE unidad_organizacional_id = %s")
    params = [unidad_id]
    if dimension_id:
        sql += " AND dimension_id = %s"
        params.append(dimension_id)
    sql += " ORDER BY dimension_id, secuencia"
    return consultar(sql, tuple(params))


def _analizar(puntos):
    """Convierte una serie cruda en una serie con lectura.

    Cada punto dice si el movimiento respecto al anterior supera el ruido.
    Los puntos SUPRIMIDOS se conservan en la serie con valor nulo: quitarlos
    haría que dos campañas no consecutivas parecieran consecutivas, y la
    variación entre ellas se leería como un solo paso.
    """
    salida = []
    anterior = None
    for punto in puntos:
        valor = _flotante(punto.get("valor_protegido"))
        ruido = _flotante(punto.get("escala_ruido")) or 0.0

        fila = {
            "campania_id": punto["campania_id"],
            "campania_nombre": punto.get("campania_nombre"),
            "secuencia": punto.get("secuencia"),
            "valor_protegido": valor,
            "n_observaciones": punto.get("n_observaciones"),
            "escala_ruido": ruido or None,
            "publicado": valor is not None,
        }

        if valor is None:
            fila["cambio"] = None
            fila["supera_el_ruido"] = None
            fila["lectura"] = ("Sin valor publicado: el grupo no alcanzo el "
                               "umbral minimo. No es cero, no hay dato.")
            # El punto suprimido NO se vuelve el "anterior": comparar contra
            # un hueco produciria un cambio inventado.
            salida.append(fila)
            continue

        if anterior is None:
            fila["cambio"] = None
            fila["supera_el_ruido"] = None
            fila["lectura"] = "Primer punto publicado de la serie."
        else:
            cambio = round(valor - anterior["valor"], 3)
            umbral = FACTOR_RUIDO * max(ruido, anterior["ruido"])
            supera = abs(cambio) > umbral if umbral > 0 else cambio != 0
            fila["cambio"] = cambio
            fila["umbral_de_ruido"] = round(umbral, 3)
            fila["supera_el_ruido"] = bool(supera)
            fila["campania_comparada"] = anterior["campania"]
            if not supera:
                fila["lectura"] = (
                    f"Cambio de {cambio:+.3f} frente a {anterior['campania']}, "
                    f"dentro del ruido (umbral {umbral:.3f}). No se puede "
                    f"afirmar que haya cambiado nada.")
            elif cambio > 0:
                fila["lectura"] = (
                    f"Subio {cambio:+.3f} frente a {anterior['campania']}, por "
                    f"encima del ruido (umbral {umbral:.3f}).")
            else:
                fila["lectura"] = (
                    f"Bajo {cambio:+.3f} frente a {anterior['campania']}, por "
                    f"debajo del ruido (umbral {umbral:.3f}).")

        anterior = {"valor": valor, "ruido": ruido,
                    "campania": punto["campania_id"]}
        salida.append(fila)
    return salida


def _resumen(serie):
    """La dirección de la serie, contando solo los cambios que superan el ruido.

    Contar todos los cambios haría que una serie plana con ruido pareciera
    tener dirección: con seis campañas, el azar produce tres subidas y tres
    bajadas, y una de ellas siempre es la última.
    """
    reales = [p for p in serie if p.get("supera_el_ruido")]
    publicados = [p for p in serie if p["publicado"]]
    subidas = sum(1 for p in reales if (p.get("cambio") or 0) > 0)
    bajadas = sum(1 for p in reales if (p.get("cambio") or 0) < 0)

    if len(publicados) < MINIMO_PUNTOS:
        direccion, lectura = "INDETERMINADA", (
            f"Hacen falta al menos {MINIMO_PUNTOS} campanias publicadas para "
            f"hablar de tendencia; hay {len(publicados)}. Con dos puntos hay "
            f"una diferencia, no una tendencia.")
    elif not reales:
        direccion, lectura = "ESTABLE", (
            "Ningun cambio de la serie supera el ruido. La unidad no muestra "
            "movimiento que se pueda distinguir del azar.")
    elif subidas and not bajadas:
        direccion, lectura = "AL_ALZA", (
            f"{subidas} cambio(s) al alza por encima del ruido, ninguno a la "
            f"baja.")
    elif bajadas and not subidas:
        direccion, lectura = "A_LA_BAJA", (
            f"{bajadas} cambio(s) a la baja por encima del ruido, ninguno al "
            f"alza. Es la combinacion que merece mirarse primero.")
    else:
        direccion, lectura = "MIXTA", (
            f"{subidas} al alza y {bajadas} a la baja por encima del ruido: "
            f"la serie se mueve, pero no en una sola direccion.")

    return {
        "direccion": direccion,
        "lectura": lectura,
        "campanias_publicadas": len(publicados),
        "campanias_suprimidas": len(serie) - len(publicados),
        "cambios_sobre_el_ruido": len(reales),
        "cambios_al_alza": subidas,
        "cambios_a_la_baja": bajadas,
    }


# =========================================================================
# Serie de una unidad
# =========================================================================
@app.get(f"{BASE}/unidad/<unidad_id>")
@requiere_permiso("AGREGADO_UNIDAD", "AGREGADO_GLOBAL", "TENDENCIA_CONSULTAR")
def serie_unidad(unidad_id):
    """Serie longitudinal de una unidad, con la lectura de cada cambio."""
    limite_consumo(maximo=120)
    if not consultar_uno("SELECT 1 AS x FROM organizacion.unidad_organizacional "
                         " WHERE unidad_organizacional_id = %s", (unidad_id,)):
        raise ErrorApi("NO_ENCONTRADO",
                       f"No existe la unidad '{unidad_id}'.", 404)
    if not _alcance_permite(unidad_id):
        _bitacora("ACCESO_DENEGADO", "RECHAZADO_PERMISO", unidad_id)
        raise ErrorApi("FUERA_DE_ALCANCE",
                       "Tu perfil no tiene alcance sobre esa unidad.", 403)

    dimension = request.args.get("dimension_id")
    puntos = _serie(unidad_id, dimension)
    if not puntos:
        return responder({
            "unidad_organizacional_id": unidad_id,
            "dimensiones": [],
            "epsilon_consumido": 0.0,
            "nota": "La unidad no tiene resultados publicados en ninguna "
                    "campania."}, 200, raiz="tendencia_respuesta")

    por_dimension = {}
    for punto in puntos:
        por_dimension.setdefault(punto["dimension_id"], []).append(punto)

    dimensiones = []
    for dimension_id, lista in sorted(por_dimension.items(),
                                      key=lambda x: str(x[0])):
        serie = _analizar(lista)
        dimensiones.append({
            "dimension_id": dimension_id,
            "serie": serie,
            "resumen": _resumen(serie),
        })

    _bitacora("TENDENCIA_CONSULTADA", "EXITO", unidad_id)
    return responder({
        "unidad_organizacional_id": unidad_id,
        "unidad": puntos[0].get("unidad_nombre"),
        "dimensiones": dimensiones,
        "total_dimensiones": len(dimensiones),
        # Cero y obligatorio: este servicio lee resultados ya publicados.
        "epsilon_consumido": 0.0,
        "nota": "Un cambio que no supera el umbral de ruido no describe un "
                "movimiento real: puede ser enteramente azar. El servicio no "
                "extrapola, porque proyectar sobre valores con ruido produce "
                "una linea que se ve cientifica y no tiene sustento.",
    }, 200, raiz="tendencia_respuesta")


# =========================================================================
# Comparación entre dos periodos
# =========================================================================
@app.post(f"{BASE}/comparar")
@requiere_permiso("AGREGADO_UNIDAD", "AGREGADO_GLOBAL", "TENDENCIA_CONSULTAR")
def comparar():
    """Compara dos campañas en todas las unidades con alcance.

    La diferencia con el comparativo de reports-service es de qué se
    compara: aquel resta dos REPORTES ya generados, con sus sellos, para
    poder auditar exactamente qué dos fotos se usaron. Este compara dos
    CAMPAÑAS leyendo la vista, que es lo que sirve para explorar antes de
    decidir qué reporte vale la pena generar.
    """
    limite_consumo(maximo=60)
    cuerpo = cuerpo_peticion()
    base_id = (cuerpo.get("campania_base") or "").strip()
    comparada_id = (cuerpo.get("campania_comparada") or "").strip()
    if not base_id or not comparada_id:
        raise ErrorApi("CAMPOS_OBLIGATORIOS",
                       "Faltan 'campania_base' y 'campania_comparada'.", 400,
                       [{"campo": "campania_base", "problema": "requerido"},
                        {"campo": "campania_comparada", "problema": "requerido"}])
    if base_id == comparada_id:
        raise ErrorApi("PARAMETRO_INVALIDO",
                       "Las dos campanias son la misma.", 400)

    for identificador in (base_id, comparada_id):
        if not consultar_uno("SELECT 1 AS x FROM catalogo.campania "
                             " WHERE campania_id = %s", (identificador,)):
            raise ErrorApi("NO_ENCONTRADO",
                           f"No existe la campania '{identificador}'.", 404)

    filas = consultar(
        "SELECT unidad_organizacional_id, unidad_nombre, dimension_id, "
        "       campania_id, valor_protegido, escala_ruido "
        "  FROM agregado.v_tendencia "
        " WHERE campania_id IN (%s, %s) "
        " ORDER BY unidad_organizacional_id, dimension_id",
        (base_id, comparada_id))

    agrupadas = {}
    for fila in filas:
        if not _alcance_permite(fila["unidad_organizacional_id"]):
            continue
        clave = (fila["unidad_organizacional_id"], fila["dimension_id"])
        agrupadas.setdefault(clave, {})[fila["campania_id"]] = fila

    comparadas, sin_comparacion = [], []
    for (unidad_id, dimension_id), por_campania in sorted(agrupadas.items(),
                                                          key=lambda x: str(x[0])):
        fila_base = por_campania.get(base_id)
        fila_comp = por_campania.get(comparada_id)
        etiqueta = {"unidad_organizacional_id": unidad_id,
                    "unidad": (fila_base or fila_comp or {}).get("unidad_nombre"),
                    "dimension_id": dimension_id}

        if not fila_base or not fila_comp:
            sin_comparacion.append({**etiqueta, "motivo":
                "la unidad no aparece en las dos campanias"})
            continue
        valor_base = _flotante(fila_base.get("valor_protegido"))
        valor_comp = _flotante(fila_comp.get("valor_protegido"))
        if valor_base is None or valor_comp is None:
            sin_comparacion.append({**etiqueta, "motivo":
                "suprimida en al menos una de las dos: la diferencia no "
                "existe, no es cero"})
            continue

        cambio = round(valor_comp - valor_base, 3)
        umbral = FACTOR_RUIDO * max(_flotante(fila_base.get("escala_ruido")) or 0,
                                    _flotante(fila_comp.get("escala_ruido")) or 0)
        comparadas.append({
            **etiqueta,
            "valor_base": valor_base,
            "valor_comparado": valor_comp,
            "cambio": cambio,
            "umbral_de_ruido": round(umbral, 3),
            "supera_el_ruido": bool(abs(cambio) > umbral) if umbral > 0
                               else cambio != 0,
        })

    reales = [c for c in comparadas if c["supera_el_ruido"]]
    _bitacora("TENDENCIA_CONSULTADA", "EXITO", f"{base_id}->{comparada_id}")
    return responder({
        "campania_base": base_id,
        "campania_comparada": comparada_id,
        "comparadas": comparadas,
        "total_comparadas": len(comparadas),
        "con_cambio_real": len(reales),
        "sin_comparacion": sin_comparacion,
        "total_sin_comparacion": len(sin_comparacion),
        "epsilon_consumido": 0.0,
        "nota": f"De {len(comparadas)} combinaciones comparables, {len(reales)} "
                f"muestran un cambio que supera el ruido. Las demas se movieron "
                f"menos de lo que el ruido puede explicar por si solo.",
    }, 200, raiz="comparacion_respuesta")


# =========================================================================
# Unidades que vienen cayendo
# =========================================================================
@app.get(f"{BASE}/descensos")
@requiere_permiso("AGREGADO_GLOBAL", "TENDENCIA_CONSULTAR",
                  "RECOMENDACION_CONSULTAR")
def descensos():
    """Unidades con caídas sostenidas por encima del ruido.

    Es la consulta que convierte este servicio en algo accionable: en
    lugar de pedir unidad por unidad, devuelve las que vienen bajando.

    «Sostenida» significa al menos dos caídas que superan el ruido, no una.
    Con una sola, cualquier serie larga califica tarde o temprano por azar.
    """
    limite_consumo(maximo=60)
    p, t = pagina()
    minimo = max(2, int(request.args.get("caidas_minimas", 2)))

    filas = consultar(
        "SELECT unidad_organizacional_id, unidad_nombre, dimension_id, "
        "       secuencia, campania_id, campania_nombre, valor_protegido, "
        "       n_observaciones, escala_ruido, variacion_absoluta, lectura "
        "  FROM agregado.v_tendencia "
        " ORDER BY unidad_organizacional_id, dimension_id, secuencia")

    agrupadas = {}
    for fila in filas:
        if not _alcance_permite(fila["unidad_organizacional_id"]):
            continue
        agrupadas.setdefault(
            (fila["unidad_organizacional_id"], fila["dimension_id"]),
            []).append(fila)

    hallazgos = []
    for (unidad_id, dimension_id), puntos in agrupadas.items():
        serie = _analizar(puntos)
        caidas = [s for s in serie
                  if s.get("supera_el_ruido") and (s.get("cambio") or 0) < 0]
        if len(caidas) < minimo:
            continue
        hallazgos.append({
            "unidad_organizacional_id": unidad_id,
            "unidad": puntos[0].get("unidad_nombre"),
            "dimension_id": dimension_id,
            "caidas_sobre_el_ruido": len(caidas),
            "caida_acumulada": round(sum(c["cambio"] for c in caidas), 3),
            "ultima_campania": caidas[-1]["campania_id"],
            "resumen": _resumen(serie),
        })

    hallazgos.sort(key=lambda h: h["caida_acumulada"])
    total = len(hallazgos)
    pagina_actual = hallazgos[(p - 1) * t: p * t]

    _bitacora("TENDENCIA_CONSULTADA", "EXITO", f"descensos:{minimo}")
    salida = sobre_pagina(pagina_actual, total, p, t, clave="descensos")
    salida["caidas_minimas"] = minimo
    salida["epsilon_consumido"] = 0.0
    salida["nota"] = ("«Sostenida» exige al menos dos caidas que superen el "
                      "ruido. Con una sola, cualquier serie larga califica "
                      "tarde o temprano por azar.")
    return responder(salida, 200, raiz="descensos_respuesta")


@app.get(f"{BASE}/criterio")
@requiere_permiso("AGREGADO_UNIDAD", "AGREGADO_GLOBAL", "TENDENCIA_CONSULTAR",
                  "PARAMETRO_ADMIN")
def criterio():
    """Qué regla usa el servicio para decidir. Publicada a propósito.

    Un servicio que clasifica cambios como reales o no reales y no dice con
    qué criterio es una caja negra, y una caja negra no se puede discutir
    en un comité ni defender ante quien recibe una intervención.
    """
    return responder({
        "factor_ruido": round(FACTOR_RUIDO, 6),
        "regla": "Un cambio se considera real si |valor_b - valor_a| > "
                 "sqrt(2) * max(escala_ruido_a, escala_ruido_b).",
        "por_que_raiz_de_dos": "Se restan dos valores con ruido de Laplace "
                               "independiente de la misma escala; la "
                               "dispersion de la diferencia es del orden de "
                               "b*sqrt(2).",
        "minimo_puntos_para_tendencia": MINIMO_PUNTOS,
        "limites_conocidos": [
            "No es una prueba de hipotesis formal y no se presenta como tal: "
            "el ruido se aplico por separado a cada punto y las muestras no "
            "son independientes entre campanias, porque en buena medida son "
            "las mismas personas.",
            "El servicio NO extrapola. Proyectar sobre valores con ruido "
            "produce una linea que se ve cientifica y no tiene sustento.",
            "Un punto suprimido no se compara ni se interpola: se conserva "
            "en la serie con valor nulo.",
        ],
        "epsilon_consumido": 0.0,
    }, 200, raiz="criterio_respuesta")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PUERTO", "8114")))
