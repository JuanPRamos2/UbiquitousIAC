"""
sync-service — sincronización desde los clientes con red intermitente.

EL PROBLEMA, DICHO CON PRECISIÓN
---------------------------------
La aplicación de escritorio y la móvil capturan respuestas donde la red
va y viene. Cuando un envío no recibe respuesta, el cliente **no puede
distinguir** dos situaciones que desde su lado se ven idénticas:

    a) la petición no llegó al servidor;
    b) la petición llegó, se aplicó, y la respuesta se perdió al volver.

En (a) hay que reenviar. En (b) reenviar duplica. Y como no se pueden
distinguir, un cliente razonable reenvía siempre. Así que el trabajo de
este servicio no es «recibir datos»: es **hacer que reenviar sea
inofensivo**.

LAS CINCO DECISIONES
--------------------
1. **La idempotencia es por clave del cliente, no por contenido.** El
   cliente genera un identificador por operación antes del primer intento
   y lo repite en cada reenvío. Comparar por contenido sería lo intuitivo
   y estaría mal: dos personas del mismo turno pueden contestar
   exactamente lo mismo, y con comparación por contenido la segunda
   respuesta legítima se descartaría como duplicada.

2. **El resultado se guarda, no solo el hecho de haber procesado.** Un
   reenvío recibe la MISMA respuesta que el primer intento. Si recibiera
   otra, el cliente tendría que decidir qué hacer con la diferencia y
   volveríamos al problema de origen.

3. **El lote no es todo o nada.** Cada renglón se resuelve por su cuenta.
   Un lote de cuarenta respuestas con una mal formada no puede perder las
   otras treinta y nueve: el cliente que las capturó sin red no tiene cómo
   recuperarlas. (`integration-service` toma la decisión opuesta, y por
   un motivo que está escrito allá.)

4. **El servidor dice qué reintentar y qué no.** Un rechazo por datos mal
   formados volverá a fallar igual: marcarlo reintentable hace que el
   cliente lo mande para siempre. Una falla temporal sí hay que
   reintentarla. Sin esa distinción el cliente reintenta lo imposible o
   abandona lo que sí habría pasado.

5. **Un conflicto no se resuelve sobrescribiendo.** Si una campaña ya fue
   respondida, la respuesta que llega después NO reemplaza a la primera.
   Último-que-escribe-gana es el reflejo habitual y aquí sería grave: esa
   primera respuesta puede haber entrado ya en un agregado publicado, y
   sobrescribirla cambiaría un número que ya salió, hacia atrás y sin
   rastro.

LO QUE ESTE SERVICIO NO HACE
-----------------------------
No guarda respuestas. Las respuestas entran por
`autoreporte.fn_registrar_autoreporte`, que es la única vía y la que
aplica las reglas (campaña abierta, consentimiento vigente, una respuesta
por campaña). Reimplementar esas reglas aquí habría creado un segundo
camino de entrada que podría divergir del primero, y el día que
divergiera, los agregados se contaminarían sin que nada fallara.
"""
import datetime as dt
import hashlib
import json
import os

from flask import g, request

from comun import (ErrorApi, VERSION_API, crear_servicio, cuerpo_peticion,
                   limite_consumo, obtener_redis, responder, requiere_permiso,
                   requiere_token)
from comun.datos import consultar, consultar_uno, cursor, ping as ping_pg

os.environ.setdefault("NOMBRE_SERVICIO", "sync-service")

ORIGENES = {"ESCRITORIO", "MOVIL", "WEB", "OTRO"}
TIPOS_OPERACION = {"AUTOREPORTE"}

# Tope de renglones por lote. No es arbitrario: un lote sin tope permite a
# un cliente mandar un archivo de cien mil renglones y tener la conexión y
# una transacción ocupadas minutos. El cliente parte el lote, que es
# justamente lo que ya sabe hacer para reintentar.
MAXIMO_POR_LOTE = int(os.environ.get("SYNC_MAXIMO_LOTE", "200"))

# Cómo se traduce cada estado de `fn_registrar_autoreporte` al resultado
# que ve el cliente, y si debe reintentar.
#
# La columna que importa es la tercera. Marcar todo como reintentable es
# el descuido fácil y produce un cliente que reenvía para siempre algo que
# nunca va a pasar; marcar nada deja perdidas las respuestas que solo
# fallaron porque la campaña todavía no abría.
TRADUCCION = {
    "REGISTRADA":           ("APLICADA",     False,
                             "Respuesta registrada."),
    "YA_RESPONDIDA":        ("EN_CONFLICTO", False,
                             "Esa campania ya tiene respuesta de ese "
                             "seudonimo. Se conserva la primera: "
                             "sobrescribirla cambiaria un dato que quizas "
                             "ya entro en un agregado publicado."),
    "SIN_CONSENTIMIENTO":   ("RECHAZADA",    False,
                             "No hay consentimiento vigente. No se "
                             "reintenta: mientras no exista, volvera a "
                             "fallar igual."),
    "SEUDONIMO_INVALIDO":   ("RECHAZADA",    False,
                             "El seudonimo no corresponde a nadie del "
                             "padron."),
    "RESPUESTA_INCOMPLETA": ("RECHAZADA",    False,
                             "Faltan reactivos del instrumento."),
    # La campaña cerrada es el único caso que sí tiene sentido reintentar:
    # una campaña programada abre más tarde, y la respuesta capturada sin
    # red minutos antes es válida en cuanto abra.
    "CAMPANIA_NO_ABIERTA":  ("RECHAZADA",    True,
                             "La campania no admite respuestas ahora. "
                             "Vale reintentar: una campania programada "
                             "abre despues."),
}


def _ping_redis():
    obtener_redis().ping()


app = crear_servicio(
    "sync-service",
    "Sincronizacion idempotente de operaciones capturadas sin red",
    comprobaciones={"postgresql": ping_pg, "redis": _ping_redis})

from contrato import montar as _montar_contrato  # noqa: E402
_montar_contrato(app)

BASE = f"/api/{VERSION_API}/sincronizacion"


def _bitacora(accion, resultado, recurso=None):
    try:
        with cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO auditoria.bitacora (actor_usuario_id, "
                " actor_perfil, accion, tipo_recurso, recurso_id, resultado, "
                " correlacion_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                ((g.get("actor") or {}).get("sub"),
                 ((g.get("actor") or {}).get("perfil") or "ANONIMO")[:30],
                 accion, "SINCRONIZACION", str(recurso) if recurso else None,
                 resultado, getattr(g, "correlacion_id", "")))
    except Exception:
        app.logger.error("No se pudo escribir en la bitacora: %s", accion)


def _huella(contenido):
    """SHA-256 del contenido normalizado.

    Solo sirve para DETECTAR que un mismo identificador de operación llegó
    con contenido distinto, que describe a un cliente que reusa
    identificadores. No se usa para deduplicar: ver la decisión 1.
    """
    texto = json.dumps(contenido, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _como_lista(valor):
    """Normaliza la lista de operaciones venga de JSON o de XML.

    El serializador XML del proyecto envuelve en plural y nombra en
    singular (`<operaciones><operacion>…`), y cuando hay un solo elemento
    el parser devuelve el diccionario en lugar de una lista de uno. Sin
    esto, un lote de una sola operación desde la aplicación de escritorio
    se leía como vacío.
    """
    if valor is None:
        return []
    if isinstance(valor, dict):
        # <operaciones><operacion>…</operacion></operaciones>
        if len(valor) == 1:
            interno = next(iter(valor.values()))
            if isinstance(interno, list):
                return interno
            if isinstance(interno, dict):
                return [interno]
        return [valor]
    if isinstance(valor, list):
        return valor
    raise ErrorApi("VALIDACION",
                   "'operaciones' tiene que ser una lista.", 422)


def _resultado_guardado(fila):
    """La respuesta que se devuelve a un reenvío: la misma de la primera vez."""
    return {
        "operacion_cliente_id": fila["operacion_cliente_id"],
        "estado": "DUPLICADA",
        "estado_original": fila["estado"],
        "mensaje": fila["mensaje"],
        "reintentable": False,
        "intentos": fila["intentos"],
        "nota": "Ya se habia aplicado. Se devuelve el resultado guardado "
                "sin volver a aplicar nada.",
    }


def _validar_operacion(op, indice):
    """Lo que se puede comprobar sin tocar la base."""
    problemas = []
    if not isinstance(op, dict):
        raise ErrorApi("VALIDACION",
                       f"La operacion {indice} no es un objeto.", 422)

    clave = str(op.get("operacion_cliente_id") or "").strip()
    tipo = str(op.get("tipo") or "AUTOREPORTE").strip().upper()
    seudonimo = str(op.get("seudonimo_id") or "").strip()
    campania = str(op.get("campania_id") or "").strip()
    valores = op.get("valores")

    if not clave:
        problemas.append("operacion_cliente_id es obligatorio: es lo que "
                         "permite que un reenvio se reconozca")
    elif len(clave) > 80:
        problemas.append("operacion_cliente_id no puede pasar de 80 "
                         "caracteres")
    if tipo not in TIPOS_OPERACION:
        problemas.append(f"tipo '{tipo}' no se sincroniza por aqui; "
                         f"admitidos: {', '.join(sorted(TIPOS_OPERACION))}")
    if not seudonimo:
        problemas.append("seudonimo_id es obligatorio")
    if not campania:
        problemas.append("campania_id es obligatorio")
    if not isinstance(valores, dict) or not valores:
        problemas.append("valores tiene que ser un objeto con al menos un "
                         "reactivo")
    # Un empleado_id en un lote de sincronización es una señal de que el
    # cliente está mandando el identificador de la persona. Se rechaza en
    # lugar de ignorarse: ignorarlo dejaría al cliente mandándolo para
    # siempre, y la primera vez que alguien lo guardara «por si acaso»
    # habría un vinculo persona-respuesta en el sistema.
    for prohibido in ("empleado_id", "correo", "nombre", "curp", "rfc"):
        if prohibido in op:
            problemas.append(
                f"'{prohibido}' no se admite: la sincronizacion va por "
                f"seudonimo. Un identificador de persona junto a una "
                f"respuesta es exactamente el vinculo que este sistema "
                f"evita tener en cualquier lado")
    return clave, tipo, seudonimo, campania, valores, problemas


def _aplicar_autoreporte(seudonimo, campania, valores):
    """Llama a la función de la base y traduce su estado.

    La función es SECURITY DEFINER y es la única vía: aquí no se
    reimplementa ninguna de sus reglas.

    OJO CON EL `commit=True`
    ------------------------
    Esta función ESCRIBE, aunque se invoque con un SELECT. El primer
    intento usaba `consultar_uno`, que abre el cursor sin commit y por
    tanto hace rollback al salir. El efecto era de los peores posibles: el
    servicio contestaba APLICADA y no quedaba nada guardado, así que el
    cliente borraba su copia local de una respuesta que nunca se escribió.
    Y no se notaba, porque la función devolvía REGISTRADA sin mentir: lo
    que se perdía era la transacción.

    Lo destapó la prueba del conflicto: la SEGUNDA respuesta del mismo
    seudónimo a la misma campaña también salía APLICADA, cuando tenía que
    chocar con la primera.
    """
    with cursor(commit=True) as cur:
        cur.execute(
            "SELECT estado, mensaje FROM "
            " autoreporte.fn_registrar_autoreporte(%s,%s,%s::jsonb)",
            (seudonimo, campania, json.dumps(valores)))
        fila = cur.fetchone()
    crudo = (fila or {}).get("estado") or "ERROR"
    mensaje_base = (fila or {}).get("mensaje") or ""
    estado, reintentable, explicacion = TRADUCCION.get(
        crudo, ("ERROR_TEMPORAL", True,
                "La base devolvio un estado que este servicio no conoce. Se "
                "marca reintentable porque no se puede afirmar que no se "
                "haya aplicado."))
    return estado, reintentable, crudo, (mensaje_base or explicacion)


# =========================================================================
# Recibir un lote
# =========================================================================
@app.post(f"{BASE}/lotes")
@requiere_permiso("AUTOREPORTE_RESPONDER")
def recibir_lote():
    """Aplica un lote de operaciones, renglón por renglón e idempotente.

    Responde 200 y no 201 a propósito: el resultado normal de un lote es
    PARCIAL —unas aplicadas, unas en conflicto, unas rechazadas—, y 201
    «creado» describiría mal algo que puede no haber creado nada.
    """
    limite_consumo(maximo=60)
    cuerpo = cuerpo_peticion()

    lote_cliente = str(cuerpo.get("lote_cliente_id") or "").strip()
    origen = str(cuerpo.get("origen") or "").strip().upper()
    operaciones = _como_lista(cuerpo.get("operaciones"))

    problemas = []
    if not lote_cliente:
        problemas.append({"campo": "lote_cliente_id",
                          "problema": "obligatorio: es lo que permite "
                                      "reenviar el lote sin duplicar"})
    if origen not in ORIGENES:
        problemas.append({"campo": "origen",
                          "problema": f"uno de: {', '.join(sorted(ORIGENES))}"})
    if not operaciones:
        problemas.append({"campo": "operaciones",
                          "problema": "el lote viene vacio"})
    if len(operaciones) > MAXIMO_POR_LOTE:
        problemas.append({"campo": "operaciones",
                          "problema": f"maximo {MAXIMO_POR_LOTE} por lote; "
                                      f"llegaron {len(operaciones)}. Partelo: "
                                      f"es lo mismo que ya haces para "
                                      f"reintentar"})
    if problemas:
        raise ErrorApi("VALIDACION", "El lote tiene campos invalidos.", 422,
                       problemas)

    # ¿Es un reenvío del lote completo? Entonces no se aplica nada: se
    # devuelve lo que se guardó la primera vez.
    previo = consultar_uno(
        "SELECT lote_id, recibidas, aplicadas, duplicadas, rechazadas, "
        "       en_conflicto, fecha_recepcion FROM sincronizacion.lote "
        " WHERE lote_cliente_id = %s", (lote_cliente,))
    if previo:
        detalle = consultar(
            "SELECT operacion_cliente_id, estado, mensaje, reintentable, "
            "       intentos FROM sincronizacion.operacion "
            " WHERE lote_id = %s ORDER BY operacion_id", (previo["lote_id"],))
        _bitacora("SINCRONIZACION_REENVIADA", "DUPLICADA", previo["lote_id"])
        return responder({
            "lote_id": previo["lote_id"],
            "lote_cliente_id": lote_cliente,
            "reenvio": True,
            "resumen": {"recibidas": previo["recibidas"],
                        "aplicadas": previo["aplicadas"],
                        "duplicadas": previo["duplicadas"],
                        "rechazadas": previo["rechazadas"],
                        "en_conflicto": previo["en_conflicto"]},
            "recibido_originalmente":
                previo["fecha_recepcion"].isoformat()
                if previo.get("fecha_recepcion") else None,
            "operaciones": [
                {"operacion_cliente_id": f["operacion_cliente_id"],
                 "estado": f["estado"], "mensaje": f["mensaje"],
                 "reintentable": f["reintentable"], "intentos": f["intentos"]}
                for f in detalle],
            "nota": "Este lote ya se habia recibido. No se aplico nada otra "
                    "vez: se devuelve el mismo resultado de la primera vez, "
                    "para que el cliente no tenga que decidir que hacer con "
                    "una respuesta distinta.",
        }, 200, raiz="lote_respuesta")

    # El formato que se registra es el que el cliente MANDÓ, no el que
    # pide de vuelta. Son cosas distintas y la que interesa guardar es la
    # primera: la aplicación de escritorio manda XML, y saber cuál de los
    # dos clientes entregó un lote es lo que permite reproducir un
    # problema de serialización.
    tipo_enviado = (request.content_type or "").split(";")[0].strip().lower()
    formato = "XML" if tipo_enviado in ("application/xml", "text/xml") \
        else "JSON"

    with cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO sincronizacion.lote (lote_cliente_id, origen, "
            " actor_usuario_id, formato, recibidas, correlacion_id) "
            "VALUES (%s,%s,%s,%s,%s,%s) RETURNING lote_id",
            (lote_cliente, origen, (g.get("actor") or {}).get("sub"),
             formato, len(operaciones), getattr(g, "correlacion_id", "")))
        lote_id = cur.fetchone()["lote_id"]

    resultados = []
    conteo = {"APLICADA": 0, "DUPLICADA": 0, "RECHAZADA": 0,
              "EN_CONFLICTO": 0, "ERROR_TEMPORAL": 0}

    for indice, op in enumerate(operaciones, start=1):
        # Un renglón malo no tumba el lote. Es la decisión 3, y aquí es
        # donde se cumple: cualquier excepción de un renglón se convierte
        # en el resultado de ese renglón.
        try:
            clave, tipo, seudonimo, campania, valores, malos = \
                _validar_operacion(op, indice)
        except ErrorApi as error:
            resultados.append({"renglon": indice, "estado": "RECHAZADA",
                               "mensaje": error.mensaje, "reintentable": False})
            conteo["RECHAZADA"] += 1
            continue

        if malos:
            resultados.append({
                "renglon": indice,
                "operacion_cliente_id": clave or None,
                "estado": "RECHAZADA",
                "mensaje": "; ".join(malos),
                "reintentable": False})
            conteo["RECHAZADA"] += 1
            # Solo se registra en la tabla si trae clave; sin clave no hay
            # idempotencia posible y registrarla sin ella impediría al
            # cliente corregir y reenviar.
            if clave:
                _registrar(lote_id, clave, tipo, None, None, "RECHAZADA",
                           "; ".join(malos), False, _huella(op))
            continue

        huella = _huella({"tipo": tipo, "seudonimo_id": seudonimo,
                          "campania_id": campania, "valores": valores})

        existente = consultar_uno(
            "SELECT operacion_cliente_id, estado, mensaje, reintentable, "
            "       intentos, huella_contenido FROM sincronizacion.operacion "
            " WHERE operacion_cliente_id = %s", (clave,))
        if existente:
            with cursor(commit=True) as cur:
                cur.execute(
                    "UPDATE sincronizacion.operacion "
                    "   SET intentos = intentos + 1, fecha_ultima = now() "
                    " WHERE operacion_cliente_id = %s", (clave,))
            guardado = _resultado_guardado(dict(existente,
                                                intentos=existente["intentos"] + 1))
            guardado["renglon"] = indice
            # Mismo identificador con otro contenido: el cliente reusa
            # claves. No se aplica el contenido nuevo —hacerlo rompería la
            # idempotencia— y queda registrado, porque describe un cliente
            # roto que de otra forma no se ve.
            if existente.get("huella_contenido") and \
                    existente["huella_contenido"] != huella:
                guardado["advertencia"] = (
                    "Este operacion_cliente_id ya se habia usado con OTRO "
                    "contenido. No se aplico el contenido nuevo: eso "
                    "rompería la idempotencia. Revisa como genera los "
                    "identificadores tu cliente.")
                _bitacora("IDENTIFICADOR_REUSADO", "DETECTADO", clave)
            resultados.append(guardado)
            conteo["DUPLICADA"] += 1
            continue

        try:
            estado, reintentable, crudo, mensaje = _aplicar_autoreporte(
                seudonimo, campania, valores)
        except Exception as error:                       # noqa: BLE001
            # Un fallo al aplicar un renglón es ERROR_TEMPORAL y
            # reintentable: no se puede afirmar que no se aplicó, y decirle
            # al cliente que no reintente perdería la respuesta.
            app.logger.error("Fallo al aplicar %s: %s", clave, error)
            estado, reintentable, crudo = "ERROR_TEMPORAL", True, "ERROR"
            mensaje = ("No se pudo aplicar ahora. Se marca reintentable "
                       "porque no se puede afirmar que no se haya aplicado.")

        _registrar(lote_id, clave, tipo, seudonimo, campania, estado,
                   mensaje, reintentable, huella)
        if estado == "EN_CONFLICTO":
            _bitacora("OPERACION_EN_CONFLICTO", "EN_CONFLICTO", clave)
        conteo[estado] = conteo.get(estado, 0) + 1
        resultados.append({"renglon": indice, "operacion_cliente_id": clave,
                           "estado": estado, "estado_base": crudo,
                           "mensaje": mensaje, "reintentable": reintentable})

    with cursor(commit=True) as cur:
        cur.execute(
            "UPDATE sincronizacion.lote SET aplicadas=%s, duplicadas=%s, "
            " rechazadas=%s, en_conflicto=%s WHERE lote_id=%s",
            (conteo["APLICADA"], conteo["DUPLICADA"], conteo["RECHAZADA"],
             conteo["EN_CONFLICTO"], lote_id))

    todo_bien = conteo["APLICADA"] == len(operaciones)
    _bitacora("SINCRONIZACION_RECIBIDA",
              "EXITO" if todo_bien else "PARCIAL", lote_id)

    return responder({
        "lote_id": lote_id,
        "lote_cliente_id": lote_cliente,
        "reenvio": False,
        "resumen": {"recibidas": len(operaciones),
                    "aplicadas": conteo["APLICADA"],
                    "duplicadas": conteo["DUPLICADA"],
                    "rechazadas": conteo["RECHAZADA"],
                    "en_conflicto": conteo["EN_CONFLICTO"],
                    "error_temporal": conteo["ERROR_TEMPORAL"]},
        "reintentar": [r["operacion_cliente_id"] for r in resultados
                       if r.get("reintentable") and r.get("operacion_cliente_id")],
        "operaciones": resultados,
        "nota": "Cada renglon se resuelve por su cuenta: un renglon mal "
                "formado no tumba el lote. Reenvia SOLO lo que viene en "
                "'reintentar'; lo demas ya tiene resultado definitivo y "
                "reenviarlo no cambia nada.",
    }, 200, raiz="lote_respuesta")


def _registrar(lote_id, clave, tipo, seudonimo, campania, estado, mensaje,
               reintentable, huella):
    """Guarda el resultado de una operación.

    La restricción única sobre `operacion_cliente_id` puede fallar si dos
    peticiones del mismo cliente corren a la vez; en ese caso el resultado
    ya está guardado por la otra y no hay nada que hacer. Se traga el
    error a propósito: la alternativa sería devolver un fallo por algo que
    de hecho salió bien.
    """
    try:
        with cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO sincronizacion.operacion (operacion_cliente_id, "
                " lote_id, tipo, seudonimo_id, campania_id, estado, mensaje, "
                " reintentable, huella_contenido) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (operacion_cliente_id) DO NOTHING",
                (clave, lote_id, tipo, seudonimo, campania, estado,
                 mensaje[:2000], reintentable, huella))
    except Exception as error:                           # noqa: BLE001
        app.logger.error("No se pudo registrar la operacion %s: %s",
                         clave, error)


# =========================================================================
# Consultar el estado de un lote
# =========================================================================
@app.get(f"{BASE}/lotes/<lote_cliente_id>")
@requiere_token
def estado_lote(lote_cliente_id):
    """Qué pasó con un lote, buscado por la clave del CLIENTE.

    Por la clave del cliente y no por el identificador interno a
    propósito: si el cliente perdió la respuesta, el identificador interno
    es justamente lo que no tiene.
    """
    limite_consumo(maximo=120)
    lote = consultar_uno(
        "SELECT * FROM sincronizacion.lote WHERE lote_cliente_id = %s",
        (lote_cliente_id,))
    if not lote:
        raise ErrorApi("NO_ENCONTRADO",
                       f"No hay registro del lote '{lote_cliente_id}'. Si lo "
                       f"enviaste y no recibiste respuesta, no llego: "
                       f"reenvialo tal cual.", 404)

    operaciones = consultar(
        "SELECT operacion_cliente_id, tipo, estado, mensaje, reintentable, "
        "       intentos FROM sincronizacion.operacion "
        " WHERE lote_id = %s ORDER BY operacion_id", (lote["lote_id"],))
    salida = dict(lote)
    salida["fecha_recepcion"] = lote["fecha_recepcion"].isoformat()
    salida["operaciones"] = [dict(o) for o in operaciones]
    salida["reintentar"] = [o["operacion_cliente_id"] for o in operaciones
                            if o["reintentable"]]
    return responder(salida, 200, raiz="lote_respuesta")


# =========================================================================
# Lo que el cliente necesita saber ANTES de enviar
# =========================================================================
@app.get(f"{BASE}/contrato-de-reintento")
@requiere_token
def contrato_de_reintento():
    """Las reglas de reenvío, publicadas.

    Está en el contrato y no en un comentario porque quien las tiene que
    cumplir es el cliente, y las dos aplicaciones cliente las implementan
    por separado. Una regla que vive solo en la cabeza de quien escribió
    el servidor se implementa distinto en cada cliente.
    """
    limite_consumo(maximo=120)
    return responder({
        "idempotencia": {
            "por": "operacion_cliente_id",
            "no_por": "contenido",
            "motivo": "Dos personas del mismo turno pueden contestar "
                      "exactamente lo mismo. Con comparacion por contenido, "
                      "la segunda respuesta legitima se descartaria como "
                      "duplicada.",
            "genera": "El CLIENTE, antes del primer intento, y lo repite "
                      "identico en cada reenvio.",
        },
        "maximo_por_lote": MAXIMO_POR_LOTE,
        "estados": {
            "APLICADA": "Se registro. No reenviar.",
            "DUPLICADA": "Ya estaba aplicada; se devolvio el resultado "
                         "guardado. No reenviar.",
            "EN_CONFLICTO": "Choco con un dato que ya existia y que no se "
                            "sobrescribe. No reenviar: reenviar no lo va a "
                            "cambiar.",
            "RECHAZADA": "No paso una validacion o una regla. Reenviar solo "
                         "si 'reintentable' viene en true.",
            "ERROR_TEMPORAL": "No se pudo aplicar ahora y no se puede "
                              "afirmar que no se haya aplicado. Reenviar: "
                              "si ya se habia aplicado, saldra DUPLICADA.",
        },
        "reintento_recomendado": {
            "espera": "exponencial, desde 2 s y hasta 5 min",
            "motivo": "Reintentar cada segundo con la red caida convierte a "
                      "muchos clientes en una carga que impide que el "
                      "servicio vuelva.",
        },
        "conflictos": {
            "politica": "La primera respuesta se conserva.",
            "no_es": "ultimo-que-escribe-gana",
            "motivo": "La primera respuesta puede haber entrado ya en un "
                      "agregado publicado. Sobrescribirla cambiaria un "
                      "numero que ya salio, hacia atras y sin rastro.",
        },
        "nota_seudonimo": "La sincronizacion va por seudonimo. Un "
                          "empleado_id, correo o nombre en el lote se "
                          "RECHAZA, no se ignora: ignorarlo dejaria al "
                          "cliente mandandolo para siempre.",
    }, 200, raiz="contrato_reintento")


# =========================================================================
# Clientes que reenvían de más
# =========================================================================
@app.get(f"{BASE}/clientes-insistentes")
@requiere_permiso("BITACORA_CONSULTAR", "PARAMETRO_ADMIN")
def clientes_insistentes():
    """Operaciones con muchos intentos: describen un cliente roto.

    Un cliente que reenvía mil veces algo ya resuelto no rompe nada —la
    idempotencia lo absorbe— y por eso no se nota. Esta vista es la única
    forma de verlo antes de que sea un problema de carga.
    """
    limite_consumo(maximo=60)
    filas = consultar(
        "SELECT o.operacion_cliente_id, o.estado, o.intentos, o.reintentable, "
        "       o.fecha_primera, o.fecha_ultima, l.origen "
        "  FROM sincronizacion.operacion o "
        "  JOIN sincronizacion.lote l USING (lote_id) "
        " WHERE o.intentos > 3 ORDER BY o.intentos DESC LIMIT 50")
    datos = []
    for fila in filas:
        d = dict(fila)
        for campo in ("fecha_primera", "fecha_ultima"):
            if isinstance(d.get(campo), (dt.date, dt.datetime)):
                d[campo] = d[campo].isoformat()
        d["sospecha"] = (
            "Reenvia algo que ya tiene resultado definitivo: el cliente no "
            "esta leyendo 'reintentable'." if not fila["reintentable"]
            else "Reintenta algo que si es reintentable; revisar por que no "
                 "termina de pasar.")
        datos.append(d)
    return responder({
        "umbral_intentos": 3,
        "total": len(datos),
        "operaciones": datos,
        "nota": "Que un cliente reenvie de mas no rompe datos: la "
                "idempotencia lo absorbe. Se vigila por carga y porque "
                "describe un cliente mal implementado.",
    }, 200, raiz="insistentes_respuesta")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PUERTO", "8120")))
