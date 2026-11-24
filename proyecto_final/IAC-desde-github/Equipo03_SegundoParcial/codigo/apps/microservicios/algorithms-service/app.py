"""
algorithms-service — motor de reglas de riesgo organizacional.

Es el microservicio de algoritmos del proyecto. Toma los agregados que ya
se publicaron, evalúa las reglas del catálogo y produce detecciones con su
explicación. Los resultados de cada corrida se guardan en MongoDB, que es
donde el proyecto almacena los resultados de algoritmos.

CUATRO DECISIONES QUE DEFINEN AL SERVICIO
-----------------------------------------
1. **Evalúa sobre lo ya publicado, así que no consume épsilon.** Las reglas
   leen `agregado.resultado_protegido` donde el estado es PUBLICADO. Si el
   motor recalculara agregados para evaluar, cada corrida gastaría
   presupuesto de privacidad y evaluar el riesgo de una organización
   costaría la capacidad de publicar resultados nuevos.

2. **Una detección sin explicación no se emite.** Cada regla produce un
   texto que dice qué valor se observó, contra qué umbral y en qué
   campaña. Nadie aprueba un plan de intervención porque un sistema lo
   diga: el especialista que lo propone tiene que poder defender por qué.

3. **Las unidades que NO se pudieron evaluar se reportan.** Si una unidad
   tiene todos sus agregados suprimidos por el umbral k, el motor no puede
   decir nada de ella. Omitirla en silencio haría creer a la organización
   que ahí no hay riesgo, cuando lo que hay es falta de datos publicables.
   Es la diferencia entre «no detectamos nada» y «no pudimos ver».

4. **La simulación no escribe.** Permite preguntar qué detectaría una regla
   con otro umbral, sin crear detecciones. Es lo que deja a un comité
   ajustar los parámetros con evidencia en lugar de a ciegas, y es de solo
   lectura a propósito: una simulación que dejara detecciones reales
   contaminaría el histórico con escenarios que nunca ocurrieron.

La evaluación en sí vive en `riesgo.fn_evaluar_unidad`, una función
SECURITY DEFINER de PostgreSQL. El servicio no reimplementa las reglas: si
lo hiciera, el portal y el microservicio podrían llegar a conclusiones
distintas sobre los mismos datos.
"""
import datetime as dt
import decimal
import os
import uuid

from flask import g, request

from comun import (ErrorApi, VERSION_API, crear_servicio, cuerpo_peticion, limite_consumo,
                   obtener_redis, pagina, responder, requiere_permiso,
                   sobre_pagina)
from comun.datos import consultar, consultar_uno, cursor, ping as ping_pg
from comun.mongo import (ASCENDING, DESCENDING, asegurar_indices, base,
                         ping as ping_mongo, verificar_sin_identidad)

os.environ.setdefault("NOMBRE_SERVICIO", "algorithms-service")

NIVELES = ("INFORMATIVO", "ATENCION", "PRIORITARIO")

INDICES = {
    "corridas_algoritmo": [
        ([("corrida_id", ASCENDING)], {"unique": True, "name": "ix_corrida_id"}),
        ([("campania_id", ASCENDING), ("fecha", DESCENDING)],
         {"name": "ix_campania_fecha"}),
        ([("unidad_organizacional_id", ASCENDING), ("fecha", DESCENDING)],
         {"name": "ix_unidad_fecha"}),
        ([("detecciones.regla_id", ASCENDING)], {"name": "ix_regla"}),
    ],
}


def _ping_redis():
    obtener_redis().ping()


app = crear_servicio(
    "algorithms-service",
    "Motor de reglas de riesgo organizacional sobre agregados ya publicados",
    # MongoDB es OPCIONAL para este servicio y esencial para los otros que
    # lo usan. El motor evalua leyendo agregados ya publicados de
    # PostgreSQL; MongoDB solo guarda el historial de corridas. Con MongoDB
    # caido, /reglas, /evaluar y /cobertura siguen funcionando, y lo unico
    # que se pierde es /corridas. Declararlo esencial sacaba de servicio a
    # una pieza que funcionaba.
    comprobaciones={"postgresql": ping_pg,
                    "mongodb": (ping_mongo, "opcional"),
                    "redis": _ping_redis})

from contrato import montar as _montar_contrato
_montar_contrato(app)

BASE = f"/api/{VERSION_API}/algoritmos"


def _bitacora(accion, resultado, recurso=None):
    try:
        with cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO auditoria.bitacora (actor_usuario_id, actor_perfil, "
                " accion, tipo_recurso, recurso_id, resultado, correlacion_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                ((g.get("actor") or {}).get("sub"),
                 ((g.get("actor") or {}).get("perfil") or "ANONIMO")[:30],
                 accion, "DETECCION", recurso, resultado,
                 getattr(g, "correlacion_id", "")))
    except Exception:
        app.logger.error("No se pudo escribir en la bitacora: %s", accion)


def _normalizar(valor):
    if isinstance(valor, (dt.datetime, dt.date)):
        return valor.isoformat()
    if isinstance(valor, decimal.Decimal):
        return float(valor)
    return valor


def _filas(sql, params=None):
    return [{k: _normalizar(v) for k, v in dict(f).items()}
            for f in consultar(sql, params)]


# Orden canónico de una detección. Es EL MISMO que declara el tipo
# Deteccion de contratos/xml/algoritmos.xsd, y existe por una razón
# concreta: una detección se construye en dos lugares distintos — la vista
# riesgo.v_recomendaciones y la función riesgo.fn_evaluar_unidad — y las dos
# devuelven sus columnas en el orden en que están escritas en el SQL, que no
# es el mismo. Un <xs:sequence> impone orden, así que el XML salía válido
# desde un endpoint e inválido desde el otro.
#
# La alternativa era relajar el esquema a <xs:all> para que el orden no
# importara. No se hizo: el orden del contrato es parte de lo que el
# contrato promete, y lo que estaba mal no era el esquema, era que el
# servicio tenía dos formas de la misma entidad. Esta tabla deja una.
CAMPOS_DETECCION = (
    "deteccion_id", "regla_id", "unidad_organizacional_id", "unidad",
    "campania_id", "nivel", "valor_observado", "explicacion",
    "tipo_intervencion", "intervencion_sugerida", "descripcion", "orden",
    "fecha_deteccion",
)


def _deteccion_canonica(fila):
    """Reordena una detección al orden del contrato y descarta lo que no está.

    Se omiten las claves ausentes en lugar de rellenarlas con nulo: en el
    esquema casi todas son minOccurs="0", y un elemento con xsi:nil dice
    «lo consulté y no hay dato», que no es lo mismo que «este endpoint no
    entrega ese campo». La diferencia la lee un cliente.
    """
    return {c: fila[c] for c in CAMPOS_DETECCION if c in fila}


def _limpiar(doc):
    doc = dict(doc)
    doc.pop("_id", None)
    for k, v in list(doc.items()):
        if isinstance(v, dt.datetime):
            doc[k] = v.isoformat()
    return doc


def _unidad_existe(unidad_id):
    return bool(consultar_uno(
        "SELECT 1 AS ok FROM organizacion.unidad_organizacional "
        " WHERE unidad_organizacional_id = %s", (unidad_id,)))


def _campania_existe(campania_id):
    return bool(consultar_uno(
        "SELECT 1 AS ok FROM catalogo.campania WHERE campania_id = %s",
        (campania_id,)))


def _alcance_permite(unidad_id):
    """El alcance sale del perfil asignado, nunca del parámetro.

    Un alcance nulo significa toda la organización, que es lo correcto para
    el especialista de bienestar: su trabajo es transversal. El líder trae
    unidad y entonces solo pasa su propio subárbol.
    """
    permisos = getattr(g, "permisos", set()) or set()
    if "AGREGADO_GLOBAL" in permisos or "PARAMETRO_ADMIN" in permisos:
        return True
    fila = consultar_uno(
        "SELECT unidad_alcance_id FROM usuarios.usuario_perfil "
        " WHERE usuario_id = %s AND perfil_id = %s",
        (g.actor.get("sub"), g.actor.get("perfil_id")))
    alcance = (fila or {}).get("unidad_alcance_id")
    if alcance is None or alcance == unidad_id:
        return True
    return bool(consultar_uno(
        "WITH RECURSIVE arbol AS ("
        "  SELECT unidad_organizacional_id FROM organizacion.unidad_organizacional"
        "   WHERE unidad_organizacional_id = %s"
        "  UNION ALL"
        "  SELECT u.unidad_organizacional_id FROM organizacion.unidad_organizacional u"
        "    JOIN arbol a ON u.unidad_padre_id = a.unidad_organizacional_id)"
        " SELECT 1 AS ok FROM arbol WHERE unidad_organizacional_id = %s",
        (alcance, unidad_id)))


# ===================================================== catálogo de reglas
@app.get(f"{BASE}/reglas")
@requiere_permiso("RECOMENDACION_CONSULTAR", "AGREGADO_UNIDAD",
                  "AGREGADO_GLOBAL", "PARAMETRO_ADMIN")
def reglas():
    """Las reglas del motor, con su condición en texto legible.

    La condición legible no es decoración: es lo que permite que alguien sin
    acceso al código entienda por qué se disparó una detección, y lo que
    hace auditable al motor.
    """
    limite_consumo(maximo=120)
    filas = _filas(
        "SELECT r.regla_id, r.nombre, r.condicion_legible, r.dimension_id, "
        "       COALESCE(d.nombre, 'Indice global') AS dimension, "
        "       r.umbral_valor, r.comparador, r.campanias_consecutivas, "
        "       r.nivel, r.activa, "
        "       (SELECT count(*) FROM riesgo.deteccion x "
        "         WHERE x.regla_id = r.regla_id) AS detecciones_historicas "
        "  FROM riesgo.regla r "
        "  LEFT JOIN catalogo.dimension d USING (dimension_id) "
        " ORDER BY r.regla_id")
    for f in filas:
        f["intervenciones_sugeridas"] = [
            x["tipo_intervencion"] for x in consultar(
                "SELECT tipo_intervencion FROM riesgo.regla_recomendacion "
                " WHERE regla_id = %s ORDER BY orden", (f["regla_id"],))]
    return responder({"reglas": filas, "total": len(filas)},
                     200, raiz="reglas_respuesta")


# ========================================================== evaluación
@app.post(f"{BASE}/evaluar")
@requiere_permiso("RECOMENDACION_CONSULTAR", "AGREGADO_GLOBAL",
                  "PARAMETRO_ADMIN")
def evaluar():
    """Corre el motor sobre una campaña, para una unidad o para todas.

    La corrida completa queda guardada en MongoDB: qué reglas se evaluaron,
    qué se detectó y qué unidades no se pudieron evaluar. Sin ese registro,
    una detección de hace tres meses no se puede explicar, porque los
    umbrales pudieron cambiar desde entonces.
    """
    limite_consumo(maximo=20)
    cuerpo = cuerpo_peticion()
    campania_id = (cuerpo.get("campania_id") or "").strip()
    unidad_id = (cuerpo.get("unidad_organizacional_id") or "").strip() or None

    problemas = []
    if not campania_id:
        problemas.append({"campo": "campania_id", "problema": "es obligatorio"})
    elif not _campania_existe(campania_id):
        problemas.append({"campo": "campania_id", "problema": "no existe"})
    if unidad_id and not _unidad_existe(unidad_id):
        problemas.append({"campo": "unidad_organizacional_id",
                          "problema": "no existe"})
    if problemas:
        raise ErrorApi("VALIDACION", "La solicitud tiene campos invalidos.",
                       422, problemas)

    if unidad_id and not _alcance_permite(unidad_id):
        _bitacora("ACCESO_DENEGADO", "RECHAZADO_PERMISO", unidad_id)
        raise ErrorApi("FUERA_DE_ALCANCE",
                       "Tu perfil no tiene alcance sobre esa unidad.", 403)

    if unidad_id:
        unidades = [unidad_id]
    else:
        # Solo las unidades con algún agregado PUBLICADO en esa campaña: las
        # demás se reportan como no evaluables más abajo.
        unidades = [f["unidad_organizacional_id"] for f in consultar(
            "SELECT DISTINCT unidad_organizacional_id "
            "  FROM agregado.resultado_protegido "
            " WHERE campania_id = %s AND estado_publicacion = 'PUBLICADO' "
            " ORDER BY unidad_organizacional_id", (campania_id,))]
        unidades = [u for u in unidades if _alcance_permite(u)]

    detecciones = []
    for u in unidades:
        for f in _filas("SELECT * FROM riesgo.fn_evaluar_unidad(%s, %s)",
                        (u, campania_id)):
            f["unidad_organizacional_id"] = u
            detecciones.append(_deteccion_canonica(f))

    no_evaluables = _no_evaluables(campania_id, unidad_id)

    documento = {
        "corrida_id": f"ALG-{uuid.uuid4().hex[:12].upper()}",
        "campania_id": campania_id,
        "unidad_organizacional_id": unidad_id,
        "unidades_evaluadas": len(unidades),
        "detecciones": detecciones,
        "total_detecciones": len(detecciones),
        "por_nivel": {n: sum(1 for d in detecciones if d["nivel"] == n)
                      for n in NIVELES},
        "no_evaluables": no_evaluables,
        "total_no_evaluables": len(no_evaluables),
        "epsilon_consumido": 0.0,
        "ejecutado_por": (g.get("actor") or {}).get("sub"),
        "perfil_ejecutor": (g.get("actor") or {}).get("perfil"),
        "fecha": dt.datetime.now(dt.timezone.utc),
        "correlacion_id": getattr(g, "correlacion_id", ""),
    }
    # El motor trabaja con unidades y agregados: nada de lo que produce
    # identifica a una persona. Se verifica antes de escribir, igual que en
    # los demas servicios que tocan MongoDB.
    verificar_sin_identidad({k: v for k, v in documento.items()
                             if k != "ejecutado_por"})
    # Si MongoDB no responde, la EVALUACION NO SE PIERDE: se devuelve igual
    # y se avisa que no quedo guardada. Lo contrario -- fallar con 500 --
    # tiraria a la basura un calculo correcto por no poder archivarlo, y
    # quien pidio la evaluacion se quedaria sin el resultado y sin saber
    # por que. La bitacora de PostgreSQL si queda en los dos casos, asi que
    # el hecho de que la corrida ocurrio no se pierde nunca.
    persistida = True
    try:
        base()["corridas_algoritmo"].insert_one(dict(documento))
    except Exception as e:
        persistida = False
        app.logger.warning("La corrida %s no se pudo guardar en MongoDB: %s",
                           documento["corrida_id"], e)
    _bitacora("DETECCION_EVALUADA", "EXITO" if persistida else "PARCIAL",
              documento["corrida_id"])

    salida = _limpiar(documento)
    if not persistida:
        salida["advertencia_persistencia"] = (
            "La evaluacion se hizo y este es su resultado, pero no quedo "
            "guardada en el historial porque MongoDB no responde. No "
            "aparecera en /corridas.")
    return responder(salida, 201, raiz="corrida_respuesta")


def _no_evaluables(campania_id, unidad_id=None):
    """Unidades convocadas que el motor no pudo evaluar, y por qué.

    Es la parte que una implementación descuidada omite. Una unidad cuyos
    agregados se suprimieron todos no aparece en las detecciones, y si no se
    reporta aquí, la organización concluye que ahí no hay problema.
    """
    sql = (
        "SELECT cu.unidad_organizacional_id, uo.nombre AS unidad, "
        "       uo.plantilla_declarada, "
        "       count(rp.resultado_id) FILTER "
        "            (WHERE rp.estado_publicacion = 'PUBLICADO') AS publicados, "
        "       count(rp.resultado_id) FILTER "
        "            (WHERE rp.estado_publicacion <> 'PUBLICADO') AS suprimidos, "
        "       CASE "
        "         WHEN count(rp.resultado_id) = 0 "
        "           THEN 'Sin agregados calculados para esta campania.' "
        "         WHEN count(rp.resultado_id) FILTER "
        "              (WHERE rp.estado_publicacion = 'PUBLICADO') = 0 "
        "           THEN 'Todos sus agregados quedaron suprimidos: el grupo no "
        "alcanza el umbral k o la campania agoto su presupuesto de epsilon. "
        "El motor no puede concluir nada, y eso NO significa que no haya "
        "riesgo.' "
        "         ELSE NULL END AS motivo "
        "  FROM catalogo.campania_unidad cu "
        "  JOIN organizacion.unidad_organizacional uo USING (unidad_organizacional_id) "
        "  LEFT JOIN agregado.resultado_protegido rp "
        "         ON rp.unidad_organizacional_id = cu.unidad_organizacional_id "
        "        AND rp.campania_id = cu.campania_id "
        " WHERE cu.campania_id = %s "
        + ("   AND cu.unidad_organizacional_id = %s " if unidad_id else "") +
        " GROUP BY cu.unidad_organizacional_id, uo.nombre, uo.plantilla_declarada "
        " HAVING count(rp.resultado_id) FILTER "
        "        (WHERE rp.estado_publicacion = 'PUBLICADO') = 0 "
        " ORDER BY uo.nombre")
    params = (campania_id, unidad_id) if unidad_id else (campania_id,)
    return _filas(sql, params)


@app.get(f"{BASE}/cobertura")
@requiere_permiso("RECOMENDACION_CONSULTAR", "AGREGADO_GLOBAL",
                  "PARAMETRO_ADMIN", "BITACORA_CONSULTAR")
def cobertura():
    """Qué pudo ver el motor y qué no, en una campaña."""
    limite_consumo(maximo=120)
    campania_id = (request.args.get("campania_id") or "").strip()
    if not campania_id:
        raise ErrorApi("PARAMETRO_FALTANTE", "Falta 'campania_id'.", 400)
    if not _campania_existe(campania_id):
        raise ErrorApi("NO_ENCONTRADO", "No existe esa campania.", 404)

    convocadas = consultar_uno(
        "SELECT count(*) AS n FROM catalogo.campania_unidad WHERE campania_id = %s",
        (campania_id,))
    no_evaluables = _no_evaluables(campania_id)
    total = (convocadas or {}).get("n", 0)
    return responder({
        "campania_id": campania_id,
        "unidades_convocadas": total,
        "unidades_evaluables": total - len(no_evaluables),
        "unidades_no_evaluables": len(no_evaluables),
        "cobertura_porcentaje": (round(100.0 * (total - len(no_evaluables)) / total, 1)
                                 if total else None),
        "no_evaluables": no_evaluables,
        "nota": "Una unidad no evaluable no es una unidad sin riesgo: es una "
                "unidad sobre la que el mecanismo de privacidad no permite "
                "concluir nada.",
    }, 200, raiz="cobertura_respuesta")


# ========================================================= detecciones
@app.get(f"{BASE}/detecciones")
@requiere_permiso("RECOMENDACION_CONSULTAR", "AGREGADO_UNIDAD",
                  "AGREGADO_GLOBAL")
def detecciones():
    """Detecciones con su explicación y las intervenciones sugeridas."""
    limite_consumo(maximo=120)
    p, t = pagina()
    condiciones, params = ["1=1"], []
    if request.args.get("campania_id"):
        condiciones.append("v.campania_id = %s")
        params.append(request.args["campania_id"])
    if request.args.get("nivel"):
        nivel = request.args["nivel"].strip().upper()
        if nivel not in NIVELES:
            raise ErrorApi("PARAMETRO_INVALIDO",
                           f"Nivel invalido. Validos: {', '.join(NIVELES)}.", 400)
        condiciones.append("v.nivel = %s")
        params.append(nivel)
    unidad = request.args.get("unidad_organizacional_id")
    if unidad:
        if not _alcance_permite(unidad):
            raise ErrorApi("FUERA_DE_ALCANCE",
                           "Tu perfil no tiene alcance sobre esa unidad.", 403)
        condiciones.append("v.unidad_organizacional_id = %s")
        params.append(unidad)

    donde = " AND ".join(condiciones)
    total = (consultar_uno(
        f"SELECT count(*) AS n FROM riesgo.v_recomendaciones v WHERE {donde}",
        tuple(params)) or {}).get("n", 0)
    filas = _filas(
        f"SELECT v.* FROM riesgo.v_recomendaciones v WHERE {donde} "
        " ORDER BY v.campania_id DESC, v.unidad, v.orden "
        " LIMIT %s OFFSET %s", tuple(params) + (t, (p - 1) * t))

    # El alcance se vuelve a aplicar sobre el resultado: sin el filtro de
    # unidad, un lider veria el arbol completo.
    filas = [_deteccion_canonica(f) for f in filas
             if _alcance_permite(f["unidad_organizacional_id"])]
    # El sobre pasa por responder() y no se devuelve tal cual: devolver el
    # diccionario hace que Flask lo serialice como JSON SIEMPRE, y entonces
    # `?formato=xml` se ignora en silencio. La aplicacion de escritorio, que
    # solo habla XML, recibia JSON y fallaba al parsear con un mensaje que
    # no apuntaba a la causa.
    return responder(sobre_pagina(filas, total, p, t, clave="detecciones"),
                     200, raiz="detecciones_respuesta")


def _historial():
    """Colección de corridas, o 503 explicativo si MongoDB no responde.

    POR QUÉ NO SE DEJA QUE FALLE SOLO
    ---------------------------------
    MongoDB es una dependencia OPCIONAL de este servicio: el motor evalúa
    leyendo agregados ya publicados de PostgreSQL, y MongoDB solo guarda el
    historial de corridas. La sonda /health/ready lo refleja y responde
    «degradado» con 200 en lugar de sacar el servicio de rotación.

    Pero declararlo opcional solo es honesto si los endpoints que SÍ lo
    necesitan lo dicen. Sin esto, una caída de MongoDB daba 500
    ERROR_INTERNO: el cliente no podía distinguir «el historial no está
    disponible ahora» de «el motor está roto», y la diferencia decide si
    conviene reintentar o avisar.
    """
    try:
        coleccion = base()["corridas_algoritmo"]
        coleccion.estimated_document_count()
        return coleccion
    except Exception as e:
        raise ErrorApi(
            "HISTORIAL_NO_DISPONIBLE",
            "El historial de corridas vive en MongoDB y MongoDB no responde. "
            "La evaluacion de riesgo sigue funcionando (lee de PostgreSQL): "
            "lo unico que no se puede consultar ahora es el registro de "
            "corridas anteriores.", 503,
            [{"campo": "mongodb", "problema": str(e)[:160]}])


# ========================================================== simulación
@app.post(f"{BASE}/simular")
@requiere_permiso("PARAMETRO_ADMIN", "AGREGADO_GLOBAL")
def simular():
    """Qué detectaría una regla con otro umbral. NO escribe nada.

    Permite a un comité mover un umbral con evidencia: cuántas unidades
    más entrarían en atención, y cuáles. La alternativa es cambiar el
    parámetro en producción y ver qué pasa, que con datos de bienestar
    laboral no es aceptable.
    """
    limite_consumo(maximo=30)
    cuerpo = cuerpo_peticion()
    regla_id = (cuerpo.get("regla_id") or "").strip()
    campania_id = (cuerpo.get("campania_id") or "").strip()
    umbral = cuerpo.get("umbral_valor")

    regla = consultar_uno(
        "SELECT regla_id, nombre, dimension_id, umbral_valor, comparador, nivel "
        "  FROM riesgo.regla WHERE regla_id = %s", (regla_id,))
    if not regla:
        raise ErrorApi("NO_ENCONTRADO", "No existe esa regla.", 404)
    if not _campania_existe(campania_id):
        raise ErrorApi("NO_ENCONTRADO", "No existe esa campania.", 404)
    if regla["umbral_valor"] is None:
        raise ErrorApi("OPERACION_NO_PERMITIDA",
                       "Esa regla no evalua un umbral sino una tendencia "
                       "sostenida: no hay un valor que simular.", 400)
    try:
        umbral = float(regla["umbral_valor"]) if umbral is None else float(umbral)
    except (TypeError, ValueError):
        raise ErrorApi("VALIDACION", "La solicitud tiene campos invalidos.", 422,
                       [{"campo": "umbral_valor", "problema": "debe ser numerico"}])

    comparador = regla["comparador"]
    if comparador not in ("<", "<=", ">", ">="):
        raise ErrorApi("OPERACION_NO_PERMITIDA",
                       f"Comparador no soportado: {comparador}.", 400)

    filas = _filas(
        "SELECT rp.unidad_organizacional_id, uo.nombre AS unidad, "
        "       rp.valor_protegido, rp.precision_advertencia "
        "  FROM agregado.resultado_protegido rp "
        "  JOIN organizacion.unidad_organizacional uo USING (unidad_organizacional_id) "
        " WHERE rp.campania_id = %s AND rp.estado_publicacion = 'PUBLICADO' "
        "   AND (%s IS NULL OR rp.dimension_id = %s) "
        "   AND (%s IS NOT NULL OR rp.dimension_id IS NULL) "
        " ORDER BY uo.nombre",
        (campania_id, regla["dimension_id"], regla["dimension_id"],
         regla["dimension_id"]))

    def dispara(v, u):
        if v is None:
            return False
        return {"<": v < u, "<=": v <= u, ">": v > u, ">=": v >= u}[comparador]

    con_umbral_actual = [f for f in filas
                         if dispara(f["valor_protegido"],
                                    float(regla["umbral_valor"]))]
    con_umbral_nuevo = [f for f in filas
                        if dispara(f["valor_protegido"], umbral)]
    nuevas = [f for f in con_umbral_nuevo if f not in con_umbral_actual]
    dejarian = [f for f in con_umbral_actual if f not in con_umbral_nuevo]

    # Advertencia honesta: una unidad cuyo valor trae advertencia de
    # precision esta cerca del ruido, y mover el umbral unas decimas la
    # mete o la saca por azar y no por su situacion real.
    cerca_del_ruido = [f for f in con_umbral_nuevo if f["precision_advertencia"]]

    return responder({
        "regla_id": regla["regla_id"],
        "nombre": regla["nombre"],
        "campania_id": campania_id,
        "comparador": comparador,
        "umbral_actual": float(regla["umbral_valor"]),
        "umbral_simulado": umbral,
        "unidades_con_valor_publicado": len(filas),
        "detectadas_con_umbral_actual": len(con_umbral_actual),
        "detectadas_con_umbral_simulado": len(con_umbral_nuevo),
        "entrarian": nuevas,
        "saldrian": dejarian,
        "con_advertencia_de_precision": len(cerca_del_ruido),
        "nota": "Simulacion de solo lectura: no se creo ninguna deteccion. "
                "Las unidades con advertencia de precision estan cerca del "
                "ruido, de modo que mover el umbral unas decimas las mete o "
                "las saca por azar y no por su situacion.",
        "epsilon_consumido": 0.0,
    }, 200, raiz="simulacion_respuesta")


# =========================================================== corridas
@app.get(f"{BASE}/corridas")
@requiere_permiso("RECOMENDACION_CONSULTAR", "AGREGADO_GLOBAL",
                  "PARAMETRO_ADMIN", "BITACORA_CONSULTAR")
def corridas():
    """Historial de corridas del motor, desde MongoDB."""
    limite_consumo(maximo=120)
    p, t = pagina()
    filtro = {}
    if request.args.get("campania_id"):
        filtro["campania_id"] = request.args["campania_id"]
    coleccion = _historial()
    total = coleccion.count_documents(filtro)
    cursor_mongo = (coleccion.find(filtro, {"detecciones": 0, "no_evaluables": 0})
                    .sort("fecha", DESCENDING).skip((p - 1) * t).limit(t))
    return responder(sobre_pagina([_limpiar(d) for d in cursor_mongo],
                                  total, p, t, clave="corridas"),
                     200, raiz="corridas_respuesta")


@app.get(f"{BASE}/corridas/<corrida_id>")
@requiere_permiso("RECOMENDACION_CONSULTAR", "AGREGADO_GLOBAL",
                  "PARAMETRO_ADMIN", "BITACORA_CONSULTAR")
def corrida(corrida_id):
    doc = _historial().find_one({"corrida_id": corrida_id})
    if not doc:
        raise ErrorApi("NO_ENCONTRADO", "No existe esa corrida.", 404)
    return responder(_limpiar(doc), 200, raiz="corrida_respuesta")


@app.post(f"{BASE}/indices")
@requiere_permiso("PARAMETRO_ADMIN")
def crear_indices():
    creados = asegurar_indices(INDICES)
    return responder({"indices": creados, "total": len(creados)},
                     200, raiz="indices_respuesta")
