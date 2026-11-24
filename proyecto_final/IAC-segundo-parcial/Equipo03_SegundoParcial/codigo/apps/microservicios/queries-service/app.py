"""
queries-service — consultas de lectura con caché en Redis.

Responsabilidad única: responder rápido las consultas que las pantallas
piden muchas veces y que cambian poco. No calcula nada: lee resultados ya
publicados y los guarda en Redis.

La restricción que define a este servicio:

    NUNCA invoca agregado.fn_calcular_agregado_protegido.

Esa función consume presupuesto de épsilon cada vez que corre. Un servicio
de consultas que la invocara gastaría presupuesto de privacidad en cada
recarga de pantalla y, al agotarlo, dejaría a la campaña sin poder publicar
resultados nuevos. Así que aquí solo se leen las vistas de resultados ya
publicados (agregado.v_tablero_unidad, v_tendencia, v_estado_presupuesto).
Quien quiera calcular un agregado nuevo pasa por el sistema web, que lo
hace de forma explícita y deja constancia.

La caché es de lectura, con TTL corto y con invalidación explícita por
recurso. Se llevan contadores de aciertos y fallos en Redis porque un
"tenemos caché" sin números no se puede defender en la demostración.
"""
import datetime as dt
import json
import os

from flask import g, request

from comun import (ErrorApi, REPETICIONES_ANORMALES, VERSION_API,
                   crear_servicio, cuerpo_peticion, k_minimo, limite_consumo,
                   obtener_redis, pagina, registrar_consulta, registrar_unidad,
                   responder, requiere_permiso, sobre_pagina,
                   verificar_diferencia)
from comun.datos import consultar, consultar_uno, cursor, ping as ping_pg

os.environ.setdefault("NOMBRE_SERVICIO", "queries-service")

PREFIJO = "consulta:"
TTL_POR_RECURSO = {
    # El tablero cambia solo cuando se publica un agregado nuevo, que es
    # una operación deliberada: un minuto de desfase es aceptable y ahorra
    # la mayoría de las consultas.
    "tablero": 60,
    "tendencia": 120,
    # El presupuesto de privacidad se consulta para decidir si se puede
    # publicar: un dato viejo aquí llevaría a creer que queda épsilon
    # cuando ya no queda. TTL muy corto a propósito.
    "presupuesto": 10,
    "participacion": 30,
    "catalogo": 300,
}


def _ping_redis():
    obtener_redis().ping()


app = crear_servicio(
    "queries-service",
    "Consultas de lectura sobre resultados ya publicados, con cache en Redis",
    comprobaciones={"postgresql": ping_pg, "redis": _ping_redis})

from contrato import montar as _montar_contrato
_montar_contrato(app)

BASE = f"/api/{VERSION_API}/consultas"


def _clave(recurso, **parametros):
    partes = [f"{k}={v}" for k, v in sorted(parametros.items()) if v not in (None, "")]
    return f"{PREFIJO}{recurso}" + (f"?{'&'.join(partes)}" if partes else "")


def _serializable(filas):
    """Las fechas y los Decimal de psycopg2 no son JSON por sí mismos."""
    import decimal
    salida = []
    for f in filas:
        d = {}
        for k, v in dict(f).items():
            if isinstance(v, (dt.date, dt.datetime)):
                d[k] = v.isoformat()
            elif isinstance(v, decimal.Decimal):
                d[k] = float(v)
            else:
                d[k] = v
        salida.append(d)
    return salida


def _con_cache(recurso, parametros, consulta_fn):
    """Lee de la caché o consulta y guarda. Devuelve (datos, origen).

    Los contadores son POR RECURSO y no globales. Un total agregado no
    sirve para decidir nada: con 90% de aciertos globales todavía puede ser
    que el presupuesto de privacidad —el de TTL más corto— se esté
    consultando siempre contra la base, que es exactamente lo que se
    querría saber.
    """
    clave = _clave(recurso, **parametros)
    r = None
    try:
        r = obtener_redis()
        crudo = r.get(clave)
        if crudo:
            try:
                r.incr(f"{PREFIJO}_metricas:{recurso}:aciertos")
            except Exception:
                pass
            return json.loads(crudo), "cache"
    except Exception:
        # Caché caída: se consulta la base y se sigue. La caché acelera,
        # no es la fuente de verdad.
        app.logger.warning("Redis no disponible; se consulta PostgreSQL")

    datos = consulta_fn()
    if r is not None:
        try:
            r.set(clave, json.dumps(datos), ex=TTL_POR_RECURSO.get(recurso, 60))
            r.incr(f"{PREFIJO}_metricas:{recurso}:fallos")
        except Exception:
            pass
    return datos, "base"


def _bitacora(accion, resultado, recurso=None):
    """Deja constancia. Nunca tumba la operación principal.

    Se registra en PostgreSQL y no en los registros de texto del proceso
    porque un rastro que vive en el disco del contenedor desaparece con el
    contenedor, y estos eventos son justamente los que alguien va a querer
    revisar después.
    """
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


def _control_inferencia(recurso, parametros, unidad_id=None):
    """Control de consultas repetidas y de ataques por diferencia.

    Las dos cosas que exige la especificación del servicio y que no
    existían: hasta ahora cada consulta se evaluaba sola, y hay información
    que ninguna consulta revela por separado pero que la combinación de dos
    sí revela. La explicación larga está en comun/inferencia.py.

    El orden importa: se verifica ANTES de leer la base. Verificar después
    significaría que el dato ya se calculó y que lo único que falta es no
    enviarlo, y basta un error de programación más adelante para que se
    envíe igual.
    """
    actor = (g.get("actor") or {}).get("sub")
    if not actor:
        return
    redis = obtener_redis()

    repeticiones = registrar_consulta(redis, actor, recurso, parametros)
    if repeticiones and repeticiones == REPETICIONES_ANORMALES:
        # Se registra UNA vez, al cruzar el umbral, y no en cada consulta
        # posterior: si no, una sola sesión insistente llena la bitácora y
        # entierra todo lo demás.
        _bitacora("CONSULTA_REPETIDA", "DETECTADO",
                  f"{recurso}:{repeticiones}")

    if unidad_id:
        try:
            verificar_diferencia(redis, actor, unidad_id, consultar_uno,
                                 k_minimo(consultar_uno))
        except ErrorApi:
            _bitacora("CONSULTA_BLOQUEADA", "RECHAZADO", unidad_id)
            raise


def _respuesta(recurso, parametros, consulta_fn, clave_datos, raiz):
    datos, origen = _con_cache(recurso, parametros, consulta_fn)
    ttl = TTL_POR_RECURSO.get(recurso, 60)
    cuerpo = {clave_datos: datos,
              "desde_cache": origen == "cache",
              "ttl_segundos": ttl,
              "consultado_en": dt.datetime.now(dt.timezone.utc).isoformat()}
    respuesta = responder(cuerpo, 200, raiz=raiz)
    # Las cabeceras permiten demostrar la caché desde el navegador, sin
    # entrar al servidor ni leer el cuerpo de la respuesta.
    respuesta.headers["X-Cache"] = "ACIERTO" if origen == "cache" else "FALLO"
    respuesta.headers["X-Cache-TTL"] = str(ttl)
    return respuesta


def _unidad_existe(unidad_id):
    """Una unidad inexistente se responde 404, no 200 con cero filas.

    La diferencia importa en la pantalla: una lista vacía deja creer que la
    unidad existe y no tuvo resultados, cuando lo que pasa es que el
    identificador está mal escrito.
    """
    return bool(consultar_uno(
        "SELECT 1 AS ok FROM organizacion.unidad_organizacional "
        " WHERE unidad_organizacional_id = %s", (unidad_id,)))


def _unidad_permitida(unidad_id):
    """Un líder solo consulta su propia unidad.

    El alcance NO se toma del parámetro sino del perfil asignado en
    usuarios.usuario_perfil: si se tomara del parámetro, bastaría cambiar
    la URL para ver el tablero de otra área.

    Un alcance nulo significa toda la organización, y es lo correcto para
    el especialista de bienestar y para el auditor: su trabajo es
    transversal. El líder sí trae unidad, y entonces solo pasa su propio
    subárbol.
    """
    permisos = getattr(g, "permisos", set())
    if "AGREGADO_GLOBAL" in permisos:
        return True
    fila = consultar_uno(
        "SELECT up.unidad_alcance_id FROM usuarios.usuario_perfil up "
        "WHERE up.usuario_id = %s AND up.perfil_id = %s",
        (g.actor.get("sub"), g.actor.get("perfil_id")))
    alcance = (fila or {}).get("unidad_alcance_id")
    if alcance is None:
        return True
    if alcance == unidad_id:
        return True
    # También se admite una unidad descendiente del alcance.
    hijo = consultar_uno(
        "WITH RECURSIVE arbol AS ("
        "  SELECT unidad_organizacional_id FROM organizacion.unidad_organizacional"
        "   WHERE unidad_organizacional_id = %s"
        "  UNION ALL"
        "  SELECT u.unidad_organizacional_id FROM organizacion.unidad_organizacional u"
        "    JOIN arbol a ON u.unidad_padre_id = a.unidad_organizacional_id)"
        " SELECT 1 AS ok FROM arbol WHERE unidad_organizacional_id = %s",
        (alcance, unidad_id))
    return bool(hijo)


# ------------------------------------------------------------- tableros
@app.get(f"{BASE}/tablero/unidad/<unidad_id>")
@requiere_permiso("AGREGADO_UNIDAD", "AGREGADO_GLOBAL")
def tablero_unidad(unidad_id):
    limite_consumo(maximo=240)
    if not _unidad_existe(unidad_id):
        raise ErrorApi("NO_ENCONTRADO",
                       f"No existe la unidad organizacional '{unidad_id}'.", 404)
    if not _unidad_permitida(unidad_id):
        raise ErrorApi("FUERA_DE_ALCANCE",
                       "Tu perfil no tiene alcance sobre esa unidad.", 403)
    campania = request.args.get("campania_id")
    _control_inferencia("tablero", {"unidad": unidad_id, "campania": campania},
                        unidad_id=unidad_id)

    def consulta():
        sql = ("SELECT unidad_organizacional_id, unidad, campania_id, secuencia, "
               "       dimension, estado_publicacion, participacion_protegida, "
               "       precision_advertencia, valor_protegido, epsilon_aplicado, "
               "       mecanismo "
               "  FROM agregado.v_tablero_unidad "
               " WHERE unidad_organizacional_id = %s")
        params = [unidad_id]
        if campania:
            sql += " AND campania_id = %s"
            params.append(campania)
        sql += " ORDER BY secuencia DESC, dimension"
        return _serializable(consultar(sql, tuple(params)))

    salida = _respuesta("tablero", {"unidad": unidad_id, "campania": campania},
                        consulta, "filas", "tablero_respuesta")
    # La unidad se anota DESPUÉS de responder: si se anotara antes y la
    # consulta fallara, el actor cargaría con una unidad que nunca recibió
    # y el control le bloquearía consultas legítimas más adelante.
    registrar_unidad(obtener_redis(), (g.get("actor") or {}).get("sub"), unidad_id)
    return salida


@app.get(f"{BASE}/tendencia")
@requiere_permiso("TENDENCIA_CONSULTAR")
def tendencia():
    limite_consumo(maximo=240)
    unidad_id = request.args.get("unidad_organizacional_id")
    if not unidad_id:
        raise ErrorApi("PARAMETRO_FALTANTE",
                       "Falta 'unidad_organizacional_id'.", 400)
    if not _unidad_existe(unidad_id):
        raise ErrorApi("NO_ENCONTRADO",
                       f"No existe la unidad organizacional '{unidad_id}'.", 404)
    if not _unidad_permitida(unidad_id):
        raise ErrorApi("FUERA_DE_ALCANCE",
                       "Tu perfil no tiene alcance sobre esa unidad.", 403)

    # El periodo se acota por campaña, porque en este sistema la campaña ES
    # el periodo de medición: cada una cubre un semestre y `secuencia` las
    # ordena. Un filtro por fechas sueltas no serviría —un agregado no
    # pertenece a un día, pertenece a la campaña que lo produjo— y daría a
    # entender que se puede cortar la serie por donde sea.
    desde = request.args.get("desde_campania")
    hasta = request.args.get("hasta_campania")
    for nombre, valor in (("desde_campania", desde), ("hasta_campania", hasta)):
        if valor and not consultar_uno(
                "SELECT 1 AS ok FROM catalogo.campania WHERE campania_id = %s",
                (valor,)):
            raise ErrorApi("CAMPANIA_NO_EXISTE",
                           f"La campania '{valor}' de '{nombre}' no existe.",
                           422)

    # La tendencia entrega la serie de la MISMA unidad a lo largo de las
    # campañas, así que sirve igual de bien para un ataque por diferencia:
    # quien tenga la serie del padre y la de las hijas puede restar en cada
    # punto. Pasa por el mismo control.
    _control_inferencia("tendencia", {"unidad": unidad_id}, unidad_id=unidad_id)

    def consulta():
        sql = ("SELECT * FROM agregado.v_tendencia "
               " WHERE unidad_organizacional_id = %s")
        params = [unidad_id]
        # Se compara por `secuencia` y no por el texto del identificador:
        # ordenar 'CAMP-2026-S10' como cadena lo pondría antes de
        # 'CAMP-2026-S2', y el recorte saldría al revés el día que haya
        # diez campañas.
        if desde:
            sql += (" AND secuencia >= (SELECT secuencia FROM "
                    " catalogo.campania WHERE campania_id = %s)")
            params.append(desde)
        if hasta:
            sql += (" AND secuencia <= (SELECT secuencia FROM "
                    " catalogo.campania WHERE campania_id = %s)")
            params.append(hasta)
        sql += " ORDER BY secuencia"
        return _serializable(consultar(sql, tuple(params)))

    # El rango entra en la clave de caché. Si no entrara, la primera
    # consulta de una unidad dejaría guardada su serie completa y la
    # siguiente, acotada, recibiría esa misma serie entera desde la caché:
    # el filtro parecería no funcionar y nadie sabría por qué.
    parametros = {"unidad": unidad_id, "desde": desde or "", "hasta": hasta or ""}
    salida = _respuesta("tendencia", parametros, consulta,
                        "puntos", "tendencia_respuesta")
    registrar_unidad(obtener_redis(), (g.get("actor") or {}).get("sub"), unidad_id)
    return salida


# -------------------------------------------- presupuesto de privacidad
@app.get(f"{BASE}/presupuesto")
@requiere_permiso("AGREGADO_UNIDAD", "AGREGADO_GLOBAL", "PARAMETRO_ADMIN")
def presupuesto():
    limite_consumo(maximo=120)

    def consulta():
        return _serializable(consultar(
            "SELECT * FROM agregado.v_estado_presupuesto "
            " ORDER BY campania_id, unidad_organizacional_id"))

    return _respuesta("presupuesto", {}, consulta, "elementos",
                      "presupuesto_respuesta")


# ------------------------------------------------------- participación
@app.get(f"{BASE}/participacion")
@requiere_permiso("AGREGADO_UNIDAD", "AGREGADO_GLOBAL", "BITACORA_CONSULTAR")
def participacion():
    """Conteos de participación por unidad y campaña.

    Son conteos, no puntajes: cuántas personas respondieron. Aun así se
    marca cuándo el grupo es demasiado chico, porque un conteo de dos en
    una unidad de tres personas ya dice demasiado sobre quién respondió.
    """
    limite_consumo(maximo=120)

    def consulta():
        return _serializable(consultar(
            "SELECT rp.campania_id, rp.unidad_organizacional_id, uo.nombre AS unidad, "
            "       MAX(rp.n_observaciones) AS respuestas, "
            "       uo.plantilla_declarada, "
            "       CASE WHEN uo.plantilla_declarada > 0 "
            "            THEN ROUND(100.0 * MAX(rp.n_observaciones) / uo.plantilla_declarada, 1) "
            "            ELSE NULL END AS cobertura_porcentaje "
            "  FROM agregado.resultado_protegido rp "
            "  JOIN organizacion.unidad_organizacional uo USING (unidad_organizacional_id) "
            " GROUP BY rp.campania_id, rp.unidad_organizacional_id, uo.nombre, "
            "          uo.plantilla_declarada "
            " ORDER BY rp.campania_id DESC, uo.nombre"))

    return _respuesta("participacion", {}, consulta, "elementos",
                      "participacion_respuesta")


# ------------------------------------------------- resumen de catálogos
@app.get(f"{BASE}/catalogo/resumen")
@requiere_permiso("INSTRUMENTO_ADMIN", "CAMPANIA_ADMIN", "UNIDAD_ADMIN",
                  "BITACORA_CONSULTAR")
def resumen_catalogo():
    limite_consumo(maximo=120)

    def consulta():
        return dict(consultar_uno(
            "SELECT (SELECT count(*) FROM organizacion.unidad_organizacional WHERE activa) AS unidades_activas,"
            "       (SELECT count(*) FROM catalogo.instrumento WHERE activo)   AS instrumentos_activos,"
            "       (SELECT count(*) FROM catalogo.reactivo WHERE activo)      AS reactivos_activos,"
            "       (SELECT count(*) FROM catalogo.campania WHERE estado = 'ABIERTA') AS campanias_abiertas,"
            "       (SELECT count(*) FROM catalogo.campania)                   AS campanias_totales,"
            "       (SELECT count(*) FROM catalogo.fuente_autorizada WHERE NOT autorizada) AS fuentes_prohibidas"))

    datos, origen = _con_cache("catalogo", {}, consulta)
    return responder({"resumen": datos, "origen": origen},
                     200, raiz="catalogo_resumen")


# ------------------------------------------------- operación de la caché
@app.get(f"{BASE}/cache/estado")
@requiere_permiso("PARAMETRO_ADMIN", "BITACORA_CONSULTAR")
def cache_estado():
    """Números de la caché, para poder demostrarla en lugar de afirmarla."""
    r = obtener_redis()
    try:
        r.ping()
        por_recurso = {}
        for recurso, ttl in sorted(TTL_POR_RECURSO.items()):
            aciertos = int(r.get(f"{PREFIJO}_metricas:{recurso}:aciertos") or 0)
            fallos = int(r.get(f"{PREFIJO}_metricas:{recurso}:fallos") or 0)
            total = aciertos + fallos
            por_recurso[recurso] = {
                "aciertos": aciertos,
                "fallos": fallos,
                "tasa_acierto": round(aciertos / total, 3) if total else 0.0,
                "ttl_segundos": ttl,
            }
        entradas = [c for c in r.scan_iter(f"{PREFIJO}*", count=500)
                    if ":_metricas" not in c]
    except Exception:
        raise ErrorApi("DEPENDENCIA_NO_DISPONIBLE",
                       "Redis no responde; no se puede reportar la cache.", 503)

    return responder({
        "entradas": len(entradas),
        "por_recurso": por_recurso,
        "redis_disponible": True,
        "claves": sorted(entradas)[:50],
    }, 200, raiz="cache_estado")


@app.post(f"{BASE}/cache/invalidar")
@requiere_permiso("PARAMETRO_ADMIN")
def cache_invalidar():
    """Invalidación explícita, por recurso o completa.

    Hace falta porque el TTL solo acota cuánto puede durar un dato viejo:
    cuando se acaba de publicar un agregado, el tablero debe reflejarlo de
    inmediato y no al minuto siguiente.
    """
    recurso = (cuerpo_peticion()).get("recurso")
    if recurso is not None and recurso not in TTL_POR_RECURSO:
        raise ErrorApi("PARAMETRO_INVALIDO",
                       f"Recurso desconocido. Validos: "
                       f"{', '.join(sorted(TTL_POR_RECURSO))}.", 400)
    patron = f"{PREFIJO}{recurso}*" if recurso else f"{PREFIJO}*"
    r = obtener_redis()
    borradas = 0
    try:
        for clave in list(r.scan_iter(patron, count=500)):
            if ":_metricas" in clave:
                continue
            borradas += r.delete(clave)
    except Exception:
        raise ErrorApi("DEPENDENCIA_NO_DISPONIBLE", "Redis no responde.", 503)
    return responder({"recurso": recurso or "todos", "entradas_borradas": borradas},
                     200, raiz="cache_respuesta")
