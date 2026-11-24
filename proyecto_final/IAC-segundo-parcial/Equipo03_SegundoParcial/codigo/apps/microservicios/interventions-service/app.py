"""
interventions-service — catálogo, planes y seguimiento de intervenciones.

QUÉ ES UNA INTERVENCIÓN AQUÍ, Y QUÉ NO PUEDE SER
-------------------------------------------------
Una intervención es una acción **sobre una unidad organizacional**:
rediseñar un turno, revisar la carga de un equipo, abrir un espacio de
acompañamiento. Nunca es una acción sobre una persona.

Eso no es una política que este servicio recuerde aplicar: es una
propiedad del modelo de datos. `intervencion.plan` no tiene columna para
un empleado ni para un seudónimo, y la garantía G1 del proyecto
(`gobernanza.fn_verificar_garantias`) comprueba contra el catálogo del
sistema que ninguna tabla del esquema `intervencion` admita una. Un
endpoint que quisiera dirigir una intervención a alguien no tendría dónde
guardarlo.

LAS CUATRO DECISIONES QUE DEFINEN AL SERVICIO
----------------------------------------------
1. **Un plan nace de una detección o de una justificación escrita.** No se
   puede crear un plan vacío. Intervenir sobre un equipo sin dejar dicho
   por qué es lo que convierte un programa de bienestar en una herramienta
   de presión, y seis meses después nadie recuerda el motivo.

2. **El estado avanza por transiciones declaradas, no libremente.** Una
   intervención no puede pasar de PROPUESTA a FINALIZADA sin haber sido
   aprobada ni ejecutada. La tabla de transiciones está abajo y se publica
   en el contrato.

3. **La evaluación compara valores PROTEGIDOS y dice cuándo no concluye.**
   Es la parte que se omite con facilidad: si el valor de antes o el de
   después vino suprimido, no hay diferencia que calcular. El servicio
   responde SIN_DATOS_SUFICIENTES en lugar de tratar la ausencia como cero,
   que daría una mejora o un empeoramiento inventados.

4. **Proponer y aprobar son permisos distintos.** Quien detecta la
   necesidad no es quien autoriza el gasto y el cambio organizacional. Con
   un solo permiso, el servicio dejaría de registrar esa separación y la
   aprobación sería un trámite.
"""
import datetime as dt
import os

from flask import g, request

from comun import (ErrorApi, VERSION_API, crear_servicio, cuerpo_peticion,
                   limite_consumo, obtener_redis, pagina, responder,
                   requiere_permiso, sobre_pagina)
from comun.datos import consultar, consultar_uno, cursor, ping as ping_pg

os.environ.setdefault("NOMBRE_SERVICIO", "interventions-service")

# Transiciones permitidas. Un estado que no aparezca aquí como destino de
# otro no se puede alcanzar, y eso es deliberado: el ciclo de vida de una
# intervención es la parte auditable del proceso.
TRANSICIONES = {
    "PROPUESTA":    {"APROBADA", "CANCELADA"},
    "APROBADA":     {"EN_EJECUCION", "CANCELADA"},
    "EN_EJECUCION": {"FINALIZADA", "CANCELADA"},
    # Una intervención terminada o cancelada no se reabre. Si hace falta
    # volver a actuar sobre la unidad, es un plan NUEVO, con su propia
    # justificación y su propia línea base. Reabrir el viejo borraría la
    # historia de lo que ya se intentó.
    "FINALIZADA":   set(),
    "CANCELADA":    set(),
}

ESTADOS_SEGUIMIENTO = {"EN_TIEMPO", "CON_RETRASO", "BLOQUEADA", "COMPLETADA"}


def _ping_redis():
    obtener_redis().ping()


app = crear_servicio(
    "interventions-service",
    "Catalogo, planes, seguimiento y evaluacion de intervenciones organizacionales",
    comprobaciones={"postgresql": ping_pg, "redis": _ping_redis})

from contrato import montar as _montar_contrato  # noqa: E402
_montar_contrato(app)

BASE = f"/api/{VERSION_API}/intervenciones"


def _bitacora(accion, resultado, recurso=None):
    try:
        with cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO auditoria.bitacora (actor_usuario_id, actor_perfil, "
                " accion, tipo_recurso, recurso_id, resultado, correlacion_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                ((g.get("actor") or {}).get("sub"),
                 ((g.get("actor") or {}).get("perfil") or "ANONIMO")[:30],
                 accion, "INTERVENCION", str(recurso) if recurso else None,
                 resultado, getattr(g, "correlacion_id", "")))
    except Exception:
        app.logger.error("No se pudo escribir en la bitacora: %s", accion)


def _alcance_permite(unidad_id):
    """El alcance sale del perfil asignado, nunca del parámetro.

    Si se tomara del parámetro, bastaría cambiar la URL para proponer una
    intervención sobre un área ajena.
    """
    actor = g.get("actor") or {}
    if actor.get("unidad_alcance") in (None, ""):
        return True
    fila = consultar_uno(
        "WITH RECURSIVE arbol AS ("
        "  SELECT unidad_organizacional_id FROM organizacion.unidad_organizacional"
        "   WHERE unidad_organizacional_id = %s"
        "  UNION ALL"
        "  SELECT h.unidad_organizacional_id"
        "    FROM organizacion.unidad_organizacional h"
        "    JOIN arbol a ON h.unidad_padre_id = a.unidad_organizacional_id)"
        " SELECT 1 AS x FROM arbol WHERE unidad_organizacional_id = %s",
        (actor["unidad_alcance"], unidad_id))
    return bool(fila)


def _plan(intervencion_id):
    return consultar_uno(
        "SELECT p.*, uo.nombre AS unidad, t.nombre AS tipo_nombre, t.ambito "
        "  FROM intervencion.plan p "
        "  JOIN organizacion.unidad_organizacional uo USING (unidad_organizacional_id) "
        "  LEFT JOIN intervencion.tipo_intervencion t "
        "         ON t.tipo_intervencion = p.tipo_intervencion "
        " WHERE p.intervencion_id = %s", (intervencion_id,))


def _serializable(filas):
    salida = []
    for fila in filas:
        limpia = {}
        for clave, valor in dict(fila).items():
            if isinstance(valor, (dt.date, dt.datetime)):
                limpia[clave] = valor.isoformat()
            elif hasattr(valor, "quantize"):          # Decimal
                limpia[clave] = float(valor)
            else:
                limpia[clave] = valor
        salida.append(limpia)
    return salida


# =========================================================================
# Catálogo de tipos
# =========================================================================
@app.get(f"{BASE}/tipos")
@requiere_permiso("INTERVENCION_PROPONER", "INTERVENCION_APROBAR",
                  "INTERVENCION_SEGUIMIENTO", "RECOMENDACION_CONSULTAR")
def tipos():
    """Catálogo de intervenciones posibles, con su ámbito.

    El ámbito se devuelve a propósito: deja ver que TODOS son
    organizacionales. No existe un tipo cuyo ámbito sea una persona, y la
    ausencia es la garantía.
    """
    limite_consumo(maximo=120)
    filas = consultar(
        "SELECT tipo_intervencion, nombre, descripcion, ambito "
        "  FROM intervencion.tipo_intervencion ORDER BY nombre")
    return responder({
        "tipos": _serializable(filas),
        "total": len(filas),
        "nota": "Todos los ambitos son organizacionales. El modelo de datos "
                "no admite una intervencion dirigida a una persona: "
                "intervencion.plan no tiene columna para un empleado ni para "
                "un seudonimo.",
    }, 200, raiz="tipos_respuesta")


# =========================================================================
# Planes
# =========================================================================
@app.get(BASE)
@requiere_permiso("INTERVENCION_PROPONER", "INTERVENCION_APROBAR",
                  "INTERVENCION_SEGUIMIENTO", "RECOMENDACION_CONSULTAR")
def listar():
    limite_consumo(maximo=120)
    p, t = pagina()
    condiciones, params = ["1=1"], []

    if request.args.get("estado"):
        estado = request.args["estado"].strip().upper()
        if estado not in TRANSICIONES:
            raise ErrorApi("PARAMETRO_INVALIDO",
                           f"Estado invalido. Validos: "
                           f"{', '.join(sorted(TRANSICIONES))}.", 400)
        condiciones.append("p.estado = %s")
        params.append(estado)

    if request.args.get("unidad_organizacional_id"):
        unidad = request.args["unidad_organizacional_id"]
        if not _alcance_permite(unidad):
            raise ErrorApi("FUERA_DE_ALCANCE",
                           "Tu perfil no tiene alcance sobre esa unidad.", 403)
        condiciones.append("p.unidad_organizacional_id = %s")
        params.append(unidad)

    donde = " AND ".join(condiciones)
    total = (consultar_uno(
        f"SELECT count(*) AS n FROM intervencion.plan p WHERE {donde}",
        tuple(params)) or {}).get("n", 0)
    filas = consultar(
        f"SELECT p.intervencion_id, p.unidad_organizacional_id, uo.nombre AS unidad, "
        f"       p.tipo_intervencion, p.estado, p.fecha_inicio, p.fecha_fin, "
        f"       p.responsable_usuario_id, p.campania_linea_base, p.fecha_creacion "
        f"  FROM intervencion.plan p "
        f"  JOIN organizacion.unidad_organizacional uo USING (unidad_organizacional_id) "
        f" WHERE {donde} ORDER BY p.fecha_creacion DESC LIMIT %s OFFSET %s",
        tuple(params) + (t, (p - 1) * t))

    # El alcance se vuelve a aplicar sobre el resultado: sin esto, un líder
    # que no filtre por unidad vería el árbol completo.
    filas = [f for f in filas if _alcance_permite(f["unidad_organizacional_id"])]
    return responder(sobre_pagina(_serializable(filas), total, p, t,
                                  clave="planes"),
                     200, raiz="planes_respuesta")


@app.get(f"{BASE}/<int:intervencion_id>")
@requiere_permiso("INTERVENCION_PROPONER", "INTERVENCION_APROBAR",
                  "INTERVENCION_SEGUIMIENTO", "RECOMENDACION_CONSULTAR")
def detalle(intervencion_id):
    """El plan con su historial de seguimiento y su evaluación."""
    limite_consumo(maximo=120)
    plan = _plan(intervencion_id)
    if not plan:
        raise ErrorApi("NO_ENCONTRADO",
                       f"No existe el plan {intervencion_id}.", 404)
    if not _alcance_permite(plan["unidad_organizacional_id"]):
        _bitacora("ACCESO_DENEGADO", "RECHAZADO_PERMISO", intervencion_id)
        raise ErrorApi("FUERA_DE_ALCANCE",
                       "Tu perfil no tiene alcance sobre esa unidad.", 403)

    seguimiento = consultar(
        "SELECT seguimiento_id, fecha_registro, estado_reportado, avance_nota, "
        "       registrado_por FROM intervencion.seguimiento "
        " WHERE intervencion_id = %s ORDER BY fecha_registro", (intervencion_id,))
    evaluacion = consultar(
        "SELECT evaluacion_id, campania_antes, campania_despues, valor_antes, "
        "       valor_despues, variacion, conclusion, nota_metodologica, "
        "       fecha_evaluacion FROM intervencion.evaluacion "
        " WHERE intervencion_id = %s ORDER BY fecha_evaluacion", (intervencion_id,))

    return responder({
        "plan": _serializable([plan])[0],
        "seguimiento": _serializable(seguimiento),
        "evaluaciones": _serializable(evaluacion),
        "transiciones_posibles": sorted(TRANSICIONES.get(plan["estado"], set())),
    }, 200, raiz="plan_respuesta")


@app.post(BASE)
@requiere_permiso("INTERVENCION_PROPONER")
def crear():
    """Propone un plan. Exige justificación y resultado esperado.

    No se puede crear un plan vacío: intervenir sobre un equipo sin dejar
    dicho por qué es lo que convierte un programa de bienestar en una
    herramienta de presión, y en seis meses nadie recuerda el motivo.
    """
    limite_consumo(maximo=30)
    cuerpo = cuerpo_peticion()

    unidad = (cuerpo.get("unidad_organizacional_id") or "").strip()
    tipo = (cuerpo.get("tipo_intervencion") or "").strip()
    justificacion = (cuerpo.get("justificacion") or "").strip()
    resultado_esperado = (cuerpo.get("resultado_esperado") or "").strip()

    problemas = []
    if not unidad:
        problemas.append({"campo": "unidad_organizacional_id",
                          "problema": "requerido"})
    if not tipo:
        problemas.append({"campo": "tipo_intervencion", "problema": "requerido"})
    if len(justificacion) < 20:
        problemas.append({"campo": "justificacion",
                          "problema": "al menos 20 caracteres: es lo que "
                                      "explica por que se interviene"})
    if len(resultado_esperado) < 20:
        problemas.append({"campo": "resultado_esperado",
                          "problema": "al menos 20 caracteres: sin el no hay "
                                      "nada contra que evaluar despues"})
    if problemas:
        raise ErrorApi("VALIDACION", "La solicitud tiene campos invalidos.",
                       422, problemas)

    if not consultar_uno("SELECT 1 AS x FROM organizacion.unidad_organizacional "
                         " WHERE unidad_organizacional_id = %s", (unidad,)):
        raise ErrorApi("UNIDAD_NO_EXISTE", f"La unidad {unidad} no existe.", 422)
    if not _alcance_permite(unidad):
        _bitacora("INTERVENCION_PROPUESTA", "RECHAZADO_PERMISO", unidad)
        raise ErrorApi("FUERA_DE_ALCANCE",
                       "Tu perfil no tiene alcance sobre esa unidad.", 403)
    if not consultar_uno("SELECT 1 AS x FROM intervencion.tipo_intervencion "
                         " WHERE tipo_intervencion = %s", (tipo,)):
        raise ErrorApi("TIPO_NO_EXISTE",
                       f"El tipo '{tipo}' no esta en el catalogo.", 422)

    campania = cuerpo.get("campania_linea_base")
    if campania and not consultar_uno(
            "SELECT 1 AS x FROM catalogo.campania WHERE campania_id = %s",
            (campania,)):
        raise ErrorApi("CAMPANIA_NO_EXISTE",
                       f"La campania {campania} no existe.", 422)

    with cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO intervencion.plan "
            " (unidad_organizacional_id, tipo_intervencion, deteccion_id, "
            "  justificacion, resultado_esperado, fecha_inicio, fecha_fin, "
            "  responsable_usuario_id, campania_linea_base) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING intervencion_id",
            (unidad, tipo, cuerpo.get("deteccion_id"), justificacion,
             resultado_esperado, cuerpo.get("fecha_inicio"),
             cuerpo.get("fecha_fin"), cuerpo.get("responsable_usuario_id"),
             campania))
        nuevo_id = cur.fetchone()["intervencion_id"]

    _bitacora("INTERVENCION_PROPUESTA", "EXITO", nuevo_id)
    return responder({"intervencion_id": nuevo_id,
                      "estado": "PROPUESTA",
                      "transiciones_posibles": sorted(TRANSICIONES["PROPUESTA"]),
                      "nota": "Una propuesta no es una aprobacion: proponer y "
                              "aprobar son permisos distintos a proposito."},
                     201, raiz="plan_creado")


@app.patch(f"{BASE}/<int:intervencion_id>/estado")
@requiere_permiso("INTERVENCION_APROBAR", "INTERVENCION_SEGUIMIENTO")
def cambiar_estado(intervencion_id):
    """Avanza el estado, solo por una transición declarada."""
    limite_consumo(maximo=60)
    cuerpo = cuerpo_peticion()
    destino = (cuerpo.get("estado") or "").strip().upper()

    plan = _plan(intervencion_id)
    if not plan:
        raise ErrorApi("NO_ENCONTRADO",
                       f"No existe el plan {intervencion_id}.", 404)
    if not _alcance_permite(plan["unidad_organizacional_id"]):
        raise ErrorApi("FUERA_DE_ALCANCE",
                       "Tu perfil no tiene alcance sobre esa unidad.", 403)

    origen = plan["estado"]
    permitidas = TRANSICIONES.get(origen, set())
    if destino not in permitidas:
        _bitacora("INTERVENCION_APROBADA", "RECHAZADO", intervencion_id)
        raise ErrorApi(
            "TRANSICION_INVALIDA",
            f"Un plan en {origen} no puede pasar a '{destino}'. "
            f"Desde {origen} solo se puede ir a: "
            f"{', '.join(sorted(permitidas)) or '(ninguno: es un estado final)'}.",
            409,
            [{"campo": "estado_actual", "problema": origen},
             {"campo": "estado_pedido", "problema": destino},
             {"campo": "permitidos", "problema": ", ".join(sorted(permitidas))}])

    # Aprobar exige el permiso de aprobar, no el de dar seguimiento. Sin
    # esta comprobacion, quien solo puede reportar avances podria aprobar.
    if destino == "APROBADA" and not _tiene("INTERVENCION_APROBAR"):
        _bitacora("INTERVENCION_APROBADA", "RECHAZADO_PERMISO", intervencion_id)
        raise ErrorApi("SIN_PERMISO",
                       "Aprobar una intervencion exige INTERVENCION_APROBAR. "
                       "Proponer y aprobar son permisos distintos: quien "
                       "detecta la necesidad no es quien autoriza el cambio.",
                       403)

    with cursor(commit=True) as cur:
        cur.execute("UPDATE intervencion.plan SET estado = %s "
                    " WHERE intervencion_id = %s", (destino, intervencion_id))

    # Dos acciones distintas, no una.
    #
    # El primer intento reusaba aqui el codigo "INTERVENCION_SEGUIMIENTO",
    # que es un PERMISO y no una accion de bitacora. Tenia dos problemas a
    # la vez: la accion no existe en auditoria.tipo_accion, asi que el
    # INSERT fallaba por llave foranea y el try se lo tragaba —ni un
    # cambio de estado quedaba registrado, en silencio—; y aunque
    # existiera, un codigo que es a la vez permiso y accion deja la
    # bitacora ambigua: quien filtre por el no sabe si esta viendo «alguien
    # uso el permiso de seguimiento» o «alguien registro un avance».
    _bitacora("INTERVENCION_APROBADA" if destino == "APROBADA"
              else "INTERVENCION_ESTADO_CAMBIADO", "EXITO", intervencion_id)
    return responder({"intervencion_id": intervencion_id,
                      "estado_anterior": origen,
                      "estado": destino,
                      "transiciones_posibles": sorted(TRANSICIONES[destino])},
                     200, raiz="plan_actualizado")


def _tiene(codigo):
    """Si el perfil de quien llama tiene ese permiso.

    Se lee de `g.permisos`, que `requiere_permiso` deja puesto tras
    CONSULTARLO en usuarios.perfil_permiso. No se lee del token: en este
    sistema los permisos no viajan dentro del JWT a proposito, porque si
    viajaran, quitarle un permiso a un perfil no surtiria efecto hasta que
    caducaran todos los tokens ya emitidos.

    El primer intento de esta funcion leia `actor["permisos"]`, que no
    existe. El efecto habria sido silencioso y feo: _tiene() siempre
    falso, y aprobar una intervencion habria devuelto 403 incluso a quien
    si tiene INTERVENCION_APROBAR.
    """
    return codigo in (g.get("permisos") or set())


# =========================================================================
# Seguimiento
# =========================================================================
@app.post(f"{BASE}/<int:intervencion_id>/seguimiento")
@requiere_permiso("INTERVENCION_SEGUIMIENTO", "INTERVENCION_APROBAR")
def registrar_seguimiento(intervencion_id):
    """Agrega una entrada al historial. Las entradas no se editan.

    Un historial editable no es un historial: si una nota se puede
    cambiar después, no sirve para reconstruir qué se sabía en cada
    momento, que es para lo único que existe.
    """
    limite_consumo(maximo=60)
    cuerpo = cuerpo_peticion()
    estado = (cuerpo.get("estado_reportado") or "").strip().upper()
    nota = (cuerpo.get("avance_nota") or "").strip()

    plan = _plan(intervencion_id)
    if not plan:
        raise ErrorApi("NO_ENCONTRADO",
                       f"No existe el plan {intervencion_id}.", 404)
    if not _alcance_permite(plan["unidad_organizacional_id"]):
        raise ErrorApi("FUERA_DE_ALCANCE",
                       "Tu perfil no tiene alcance sobre esa unidad.", 403)

    problemas = []
    if estado not in ESTADOS_SEGUIMIENTO:
        problemas.append({"campo": "estado_reportado",
                          "problema": f"debe ser uno de: "
                                      f"{', '.join(sorted(ESTADOS_SEGUIMIENTO))}"})
    if len(nota) < 10:
        problemas.append({"campo": "avance_nota",
                          "problema": "al menos 10 caracteres: un avance sin "
                                      "descripcion no se puede leer despues"})
    if problemas:
        raise ErrorApi("VALIDACION", "La solicitud tiene campos invalidos.",
                       422, problemas)

    if plan["estado"] not in ("APROBADA", "EN_EJECUCION"):
        raise ErrorApi("ESTADO_INCOMPATIBLE",
                       f"No se puede registrar avance de un plan en "
                       f"{plan['estado']}: todavia no empezo o ya termino.",
                       409)

    with cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO intervencion.seguimiento "
            " (intervencion_id, estado_reportado, avance_nota, registrado_por) "
            "VALUES (%s,%s,%s,%s) RETURNING seguimiento_id",
            (intervencion_id, estado, nota, (g.get("actor") or {}).get("sub")))
        nuevo_id = cur.fetchone()["seguimiento_id"]

    _bitacora("INTERVENCION_AVANCE", "EXITO", intervencion_id)
    return responder({"seguimiento_id": nuevo_id,
                      "intervencion_id": intervencion_id,
                      "estado_reportado": estado},
                     201, raiz="seguimiento_creado")


# =========================================================================
# Evaluación
# =========================================================================
@app.post(f"{BASE}/<int:intervencion_id>/evaluacion")
@requiere_permiso("INTERVENCION_APROBAR", "AGREGADO_GLOBAL")
def evaluar(intervencion_id):
    """Compara el antes y el después sobre valores YA PUBLICADOS.

    Dos cosas que este endpoint NO hace, y que son el motivo de que exista
    en lugar de un cálculo en una pantalla:

      · No consume presupuesto de épsilon. Lee `agregado.v_tablero_unidad`,
        que son resultados ya publicados. Si evaluara llamando a la función
        de cálculo, evaluar una intervención gastaría privacidad y, al
        agotarla, dejaría a la campaña sin poder publicar.

      · No trata un valor suprimido como cero. Si el antes o el después
        vino suprimido, no hay diferencia que calcular, y el servicio lo
        dice: SIN_DATOS_SUFICIENTES. Tratarlo como cero produciría una
        mejora o un empeoramiento inventados, y sobre eso se tomarían
        decisiones.
    """
    limite_consumo(maximo=30)
    cuerpo = cuerpo_peticion()
    antes = (cuerpo.get("campania_antes") or "").strip()
    despues = (cuerpo.get("campania_despues") or "").strip()
    dimension = (cuerpo.get("dimension_id") or "").strip() or None

    plan = _plan(intervencion_id)
    if not plan:
        raise ErrorApi("NO_ENCONTRADO",
                       f"No existe el plan {intervencion_id}.", 404)
    if not _alcance_permite(plan["unidad_organizacional_id"]):
        raise ErrorApi("FUERA_DE_ALCANCE",
                       "Tu perfil no tiene alcance sobre esa unidad.", 403)
    if not antes or not despues:
        raise ErrorApi("CAMPOS_OBLIGATORIOS",
                       "Faltan 'campania_antes' y 'campania_despues'.", 400,
                       [{"campo": "campania_antes", "problema": "requerido"},
                        {"campo": "campania_despues", "problema": "requerido"}])

    # Una evaluacion por plan: `intervencion.evaluacion` tiene restriccion
    # UNIQUE sobre intervencion_id. Sin esta comprobacion, la segunda
    # evaluacion reventaba con una violacion de unicidad, que sale como 500
    # y con el texto de PostgreSQL asomando en la respuesta.
    #
    # Y el limite es correcto, no un estorbo: si se pudiera evaluar el mismo
    # plan tantas veces como se quisiera, cada una con otro par de
    # campanias, bastaria probar pares hasta encontrar el que deja bien a la
    # intervencion. La evaluacion es el cierre del plan, y se hace una vez.
    if consultar_uno("SELECT evaluacion_id FROM intervencion.evaluacion "
                     " WHERE intervencion_id = %s", (intervencion_id,)):
        raise ErrorApi(
            "EVALUACION_YA_EXISTE",
            f"El plan {intervencion_id} ya esta evaluado. Se admite una sola "
            f"evaluacion por plan: si se pudiera repetir con otro par de "
            f"campanias, bastaria probar pares hasta encontrar el que deja "
            f"bien a la intervencion. Para volver a medir la unidad, es un "
            f"plan nuevo con su propia linea base.", 409)

    unidad = plan["unidad_organizacional_id"]
    sql = ("SELECT valor_protegido, estado_publicacion "
           "  FROM agregado.v_tablero_unidad "
           " WHERE unidad_organizacional_id = %s AND campania_id = %s")
    params_a, params_b = [unidad, antes], [unidad, despues]
    if dimension:
        sql += " AND dimension = %s"
        params_a.append(dimension)
        params_b.append(dimension)

    fila_a = consultar_uno(sql, tuple(params_a))
    fila_b = consultar_uno(sql, tuple(params_b))

    valor_a = fila_a.get("valor_protegido") if fila_a else None
    valor_b = fila_b.get("valor_protegido") if fila_b else None

    if valor_a is None or valor_b is None:
        faltante = []
        if valor_a is None:
            faltante.append(f"{antes} ({(fila_a or {}).get('estado_publicacion') or 'sin fila'})")
        if valor_b is None:
            faltante.append(f"{despues} ({(fila_b or {}).get('estado_publicacion') or 'sin fila'})")
        _bitacora("INTERVENCION_EVALUADA", "GRUPO_INSUFICIENTE", intervencion_id)
        return responder({
            "intervencion_id": intervencion_id,
            "conclusion": "SIN_DATOS_SUFICIENTES",
            "sin_valor_en": faltante,
            "epsilon_consumido": 0.0,
            "nota": "No hay valor publicado en al menos una de las dos "
                    "campanias, asi que no hay diferencia que calcular. NO se "
                    "toma como cero: un valor suprimido es ausencia de dato, y "
                    "tratarlo como cero produciria una mejora o un "
                    "empeoramiento inventados.",
        }, 200, raiz="evaluacion_respuesta")

    valor_a, valor_b = float(valor_a), float(valor_b)
    variacion = round(valor_b - valor_a, 3)
    # La escala es 1..5 y un valor MAS ALTO es mejor en este instrumento.
    if variacion > 0:
        conclusion = "MEJORA"
    elif variacion < 0:
        conclusion = "DETERIORO"
    else:
        conclusion = "SIN_CAMBIO"

    nota = ("Comparacion entre valores PROTEGIDOS: los dos llevan ruido de "
            "Laplace. Una variacion pequena puede ser enteramente ruido; "
            "trends-service dice si supera el umbral. Esta evaluacion no "
            "atribuye causalidad: registra que la unidad se movio despues de "
            "la intervencion, no que se movio POR la intervencion.")

    with cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO intervencion.evaluacion "
            " (intervencion_id, campania_antes, campania_despues, valor_antes, "
            "  valor_despues, conclusion, nota_metodologica) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING evaluacion_id",
            (intervencion_id, antes, despues, valor_a, valor_b, conclusion, nota))
        nuevo_id = cur.fetchone()["evaluacion_id"]

    _bitacora("INTERVENCION_EVALUADA", "EXITO", intervencion_id)
    return responder({
        "evaluacion_id": nuevo_id,
        "intervencion_id": intervencion_id,
        "campania_antes": antes, "campania_despues": despues,
        "valor_antes": valor_a, "valor_despues": valor_b,
        "variacion": variacion,
        "conclusion": conclusion,
        "nota_metodologica": nota,
        "epsilon_consumido": 0.0,
    }, 201, raiz="evaluacion_respuesta")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PUERTO", "8115")))
