"""
monitoring-service — salud, latencia y errores de los demás componentes.

QUÉ RESUELVE
------------
Cada servicio tiene su sonda `/health/ready` con tres estados —listo,
degradado, no_listo— y eso ya estaba bien. Lo que no existía era quien las
mire todas: para saber si el sistema está arriba había que abrir trece
puertos a mano, y eso significa que nadie lo hacía.

LAS CINCO DECISIONES
--------------------
1. **Este servicio no es una fuente de verdad, es un espejo.** No guarda
   un estado propio de «arriba» o «abajo»: pregunta y reporta lo que le
   contestan, con la hora. Si guardara su propio juicio, habría dos
   versiones de la salud del sistema y la gente creería la equivocada.

2. **Que un servicio esté caído NO pone a este en no_listo.** Es el error
   obvio y es grave: si monitoring se declarara no listo porque vigila
   algo caído, el orquestador lo sacaría de servicio y perderíamos la
   vista justo cuando hace falta. Su propia sonda mira solo sus propias
   dependencias.

3. **«degradado» se distingue de «caído», porque se arreglan distinto.**
   Un servicio degradado atiende con una dependencia opcional caída y no
   hay que tocarlo con urgencia. Mirar solo el código HTTP juntaría los
   dos: la sonda devuelve 200 en los dos casos, y el estado viene en el
   cuerpo.

4. **No expone datos, solo estado operativo.** Ni un agregado, ni un
   nombre, ni un correo. Un panel de monitoreo suele ser lo primero que se
   abre sin autenticación «porque solo son métricas», y en este sistema
   eso sería una fuga: saber que una unidad tiene datos publicados ya dice
   algo de esa unidad. Por eso todo exige token.

5. **Las latencias se miden desde aquí y se dicen como tales.** No son el
   tiempo que ve un usuario: son el tiempo entre este contenedor y el
   otro, en la red interna. Presentarlas como «tiempo de respuesta» haría
   tomar decisiones con un número que no mide lo que parece.
"""
import concurrent.futures as futuros
import datetime as dt
import os
import time
import urllib.error
import urllib.request

from flask import g, request

from comun import (ErrorApi, VERSION_API, crear_servicio, limite_consumo,
                   obtener_redis, responder, requiere_permiso, requiere_token)
from comun.datos import consultar, consultar_uno, cursor, ping as ping_pg

os.environ.setdefault("NOMBRE_SERVICIO", "monitoring-service")

# Los componentes vigilados, con el puerto que publica el compose de
# desarrollo. En Docker se resuelven por nombre de servicio y el puerto
# interno es 8000 para todos; fuera de Docker cada uno vive en su puerto.
# Las dos formas se contemplan porque la demostración se hace de las dos
# maneras y un monitor que solo sirva en una no sirve de nada.
COMPONENTES = (
    ("auth-service",          8101),
    ("users-service",         8102),
    ("catalog-service",       8103),
    ("main-process-service",  8104),
    ("documents-service",     8105),
    ("notifications-service", 8106),
    ("queries-service",       8107),
    ("reports-service",       8108),
    ("algorithms-service",    8109),
    ("consent-service",       8110),
    ("privacy-service",       8111),
    ("survey-service",        8112),
    ("indicators-service",    8113),
    ("trends-service",        8114),
    ("interventions-service", 8115),
    ("support-service",       8116),
    ("organizational-service", 8117),
    ("audit-service",         8118),
    ("data-governance-service", 8119),
    ("export-service",        8121),
    ("configuration-service", 8122),
    ("integration-service",   8124),
    ("sync-service",          8120),
)

# Tiempo máximo de espera por sonda. Corto a propósito: una sonda que
# tarda cinco segundos ya es un problema, y esperarla cinco segundos
# multiplicado por quince componentes convertiría este endpoint en algo
# que nadie abre porque tarda un minuto.
ESPERA_SEGUNDOS = float(os.environ.get("MONITOREO_ESPERA", "2.5"))

# Umbral para marcar una latencia como alta. No es un límite: es una
# etiqueta, y está aquí para que quien lea la lista no tenga que comparar
# milisegundos a ojo.
LATENCIA_ALTA_MS = float(os.environ.get("MONITOREO_LATENCIA_ALTA", "800"))


def _ping_redis():
    obtener_redis().ping()


app = crear_servicio(
    "monitoring-service",
    "Salud, latencia y errores de los componentes, y estado de las "
    "dependencias compartidas",
    # Solo sus PROPIAS dependencias. Ver la decisión 2 del encabezado: si
    # los quince componentes vigilados estuvieran aquí, un servicio caído
    # pondría a este en no_listo y el orquestador lo sacaría de servicio
    # justo cuando hace falta verlo.
    comprobaciones={"postgresql": ping_pg, "redis": _ping_redis})

from contrato import montar as _montar_contrato  # noqa: E402
_montar_contrato(app)

BASE = f"/api/{VERSION_API}/monitoreo"


def _url_de(nombre, puerto):
    """La URL de la sonda, por nombre en Docker y por puerto fuera.

    La variable de entorno gana, para que un despliegue con otros nombres
    no obligue a tocar el código.
    """
    explicita = os.environ.get(
        f"{nombre.replace('-', '_').upper()}_URL")
    if explicita:
        return f"{explicita.rstrip('/')}/health/ready"
    if os.environ.get("MONITOREO_EN_DOCKER", "").lower() in ("1", "true", "si"):
        return f"http://{nombre}:8000/health/ready"
    base = os.environ.get("MONITOREO_HOST", "127.0.0.1")
    return f"http://{base}:{puerto}/health/ready"


def _sondear(nombre, puerto):
    """Pregunta a un componente y reporta lo que contesta.

    Nunca lanza. Un fallo al sondear ES el dato que hay que reportar: si
    esta función propagara el error, un componente caído tumbaría la
    respuesta entera y el panel no mostraría ninguno de los que sí están.
    """
    import json
    url = _url_de(nombre, puerto)
    inicio = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=ESPERA_SEGUNDOS) as respuesta:
            ms = round((time.perf_counter() - inicio) * 1000, 1)
            cuerpo = json.loads(respuesta.read().decode("utf-8") or "{}")
            # El estado se lee del CUERPO y no se deduce del código. La
            # sonda devuelve 200 tanto para «listo» como para
            # «degradado», y deducirlo del código juntaría los dos justo
            # cuando la diferencia es lo único que importa.
            estado = cuerpo.get("estado") or "desconocido"
            return {
                "componente": nombre,
                "estado": estado,
                "http": respuesta.status,
                "latencia_ms": ms,
                "latencia_alta": ms > LATENCIA_ALTA_MS,
                "dependencias": cuerpo.get("dependencias") or {},
                "degradado_por": cuerpo.get("degradado_por") or [],
                "falta": cuerpo.get("falta") or [],
            }
    except urllib.error.HTTPError as error:
        ms = round((time.perf_counter() - inicio) * 1000, 1)
        cuerpo = {}
        try:
            cuerpo = json.loads(error.read().decode("utf-8") or "{}")
        except Exception:
            pass
        # Un 503 con cuerpo es un «no_listo» que SÍ contestó: el servicio
        # está vivo y dice qué le falta. Es distinto de uno caído, y
        # mezclarlos haría buscar el problema en el lugar equivocado.
        return {
            "componente": nombre,
            "estado": cuerpo.get("estado") or "no_listo",
            "http": error.code,
            "latencia_ms": ms,
            "latencia_alta": ms > LATENCIA_ALTA_MS,
            "dependencias": cuerpo.get("dependencias") or {},
            "degradado_por": cuerpo.get("degradado_por") or [],
            "falta": cuerpo.get("falta") or [],
        }
    except Exception as error:
        return {
            "componente": nombre,
            "estado": "sin_respuesta",
            "http": None,
            "latencia_ms": round((time.perf_counter() - inicio) * 1000, 1),
            "latencia_alta": False,
            "error": str(error)[:200],
            "dependencias": {},
            "degradado_por": [],
            "falta": [],
        }


def _sondear_todos():
    """En paralelo: en serie, quince sondas de 2.5 s son 37 segundos.

    Y con quince esperas en serie el peor caso del panel depende de
    CUÁNTOS componentes estén caídos, que es justo cuando hay que abrirlo
    rápido.
    """
    with futuros.ThreadPoolExecutor(max_workers=len(COMPONENTES)) as piscina:
        return list(piscina.map(lambda c: _sondear(*c), COMPONENTES))


# =========================================================================
# El panel
# =========================================================================
@app.get(f"{BASE}/componentes")
@requiere_token
def componentes():
    """El estado de cada componente, con su latencia y sus dependencias.

    Pide token porque un panel de monitoreo suele ser lo primero que se
    abre sin autenticación «porque solo son métricas». Aquí eso sería una
    fuga: saber que una unidad tiene datos publicados ya dice algo de esa
    unidad.
    """
    limite_consumo(maximo=120)
    filas = _sondear_todos()

    conteo = {}
    for fila in filas:
        conteo[fila["estado"]] = conteo.get(fila["estado"], 0) + 1

    # El veredicto global se calcula aquí para que no lo calcule cada
    # pantalla a su manera. Un «degradado» no es un problema urgente y un
    # «sin_respuesta» sí: juntarlos en un semáforo de dos colores haría
    # que se atendieran igual.
    if conteo.get("sin_respuesta") or conteo.get("no_listo"):
        veredicto = "con_fallas"
    elif conteo.get("degradado"):
        veredicto = "degradado"
    elif conteo.get("desconocido"):
        veredicto = "incierto"
    else:
        veredicto = "operativo"

    return responder({
        "veredicto": veredicto,
        "momento": dt.datetime.now(dt.timezone.utc).isoformat(),
        "total": len(filas),
        "por_estado": conteo,
        "componentes": sorted(filas, key=lambda f: f["componente"]),
        "nota_latencia":
            f"Las latencias se miden DESDE este contenedor, en la red "
            f"interna, con una espera maxima de {ESPERA_SEGUNDOS} s. No son "
            f"el tiempo que ve un usuario: presentarlas como «tiempo de "
            f"respuesta» haria tomar decisiones con un numero que no mide "
            f"eso. Se marcan como altas por encima de {LATENCIA_ALTA_MS} ms.",
        "nota_estados":
            "listo: todo responde. degradado: atiende con una dependencia "
            "OPCIONAL caida, y devuelve 200 a proposito. no_listo: le falta "
            "una dependencia esencial y devuelve 503, pero CONTESTO. "
            "sin_respuesta: no contesto, que es otra cosa y se arregla en "
            "otro lugar.",
    }, 200, raiz="monitoreo_respuesta")


@app.get(f"{BASE}/componentes/<nombre>")
@requiere_token
def componente(nombre):
    """Una sonda sola, para cuando ya se sabe a quién mirar."""
    limite_consumo(maximo=120)
    conocidos = dict(COMPONENTES)
    if nombre not in conocidos:
        raise ErrorApi("COMPONENTE_NO_EXISTE",
                       f"'{nombre}' no esta en la lista de componentes "
                       f"vigilados. Conocidos: "
                       f"{', '.join(sorted(conocidos))}.", 404)
    fila = _sondear(nombre, conocidos[nombre])
    fila["momento"] = dt.datetime.now(dt.timezone.utc).isoformat()
    fila["url_sondeada"] = _url_de(nombre, conocidos[nombre])
    return responder(fila, 200, raiz="componente_respuesta")


# =========================================================================
# Las dependencias compartidas
# =========================================================================
@app.get(f"{BASE}/dependencias")
@requiere_token
def dependencias():
    """PostgreSQL, Redis y MongoDB, medidos desde aquí.

    Las tres sostienen a todos los componentes, así que cuando algo falla
    en varios a la vez, el sitio donde mirar es este y no quince sondas.
    """
    limite_consumo(maximo=120)
    salida = {}

    inicio = time.perf_counter()
    try:
        ping_pg()
        salida["postgresql"] = {
            "ok": True,
            "latencia_ms": round((time.perf_counter() - inicio) * 1000, 1)}
    except Exception as error:
        salida["postgresql"] = {"ok": False, "error": str(error)[:200]}

    inicio = time.perf_counter()
    try:
        _ping_redis()
        salida["redis"] = {
            "ok": True,
            "latencia_ms": round((time.perf_counter() - inicio) * 1000, 1)}
    except Exception as error:
        salida["redis"] = {"ok": False, "error": str(error)[:200]}

    inicio = time.perf_counter()
    try:
        from comun.mongo import ping as ping_mongo
        ping_mongo()
        salida["mongodb"] = {
            "ok": True,
            "latencia_ms": round((time.perf_counter() - inicio) * 1000, 1),
            "nota": "Dependencia OPCIONAL de documents-service, "
                    "notifications-service y algorithms-service: con "
                    "MongoDB caido los tres siguen atendiendo y se "
                    "declaran degradados, no caidos."}
    except Exception as error:
        salida["mongodb"] = {
            "ok": False, "error": str(error)[:200],
            "nota": "Que este caido NO deja el sistema fuera de servicio: "
                    "es opcional para los tres componentes que lo usan."}

    esenciales_mal = [n for n in ("postgresql", "redis")
                      if not salida[n].get("ok")]
    return responder({
        "veredicto": "con_fallas" if esenciales_mal else
                     ("degradado" if not salida["mongodb"].get("ok")
                      else "operativo"),
        "momento": dt.datetime.now(dt.timezone.utc).isoformat(),
        "dependencias": salida,
        "esenciales_caidas": esenciales_mal,
    }, 200, raiz="dependencias_respuesta")


# =========================================================================
# Errores recientes, leídos de la bitácora
# =========================================================================
@app.get(f"{BASE}/errores")
@requiere_permiso("BITACORA_CONSULTAR", "PARAMETRO_ADMIN")
def errores():
    """Rechazos y fallos recientes, agrupados por acción y resultado.

    Sale de `auditoria.bitacora` y no de un contador en memoria. Un
    contador en memoria se pierde al reiniciar el proceso, que es
    justamente lo que pasa cuando algo va mal, y entonces el dato
    desaparece en el momento en que hacía falta.

    Exige BITACORA_CONSULTAR: aunque solo sean conteos, un conteo de
    rechazos por unidad ya dice en qué unidad está pasando algo.
    """
    limite_consumo(maximo=60)
    try:
        horas = int(request.args.get("horas", 24))
    except (TypeError, ValueError):
        raise ErrorApi("PARAMETRO_INVALIDO", "'horas' debe ser un entero.", 400)
    if not 1 <= horas <= 168:
        raise ErrorApi("PARAMETRO_INVALIDO",
                       "'horas' va de 1 a 168 (una semana).", 400)

    filas = consultar(
        "SELECT accion, resultado, count(*) AS n, max(fecha_hora) AS ultimo "
        "  FROM auditoria.bitacora "
        " WHERE fecha_hora > now() - make_interval(hours => %s) "
        "   AND resultado <> 'EXITO' "
        " GROUP BY accion, resultado ORDER BY n DESC LIMIT 50", (horas,))

    total = (consultar_uno(
        "SELECT count(*) AS n FROM auditoria.bitacora "
        " WHERE fecha_hora > now() - make_interval(hours => %s)",
        (horas,)) or {}).get("n", 0)

    datos = []
    for fila in filas:
        d = dict(fila)
        if isinstance(d.get("ultimo"), (dt.date, dt.datetime)):
            d["ultimo"] = d["ultimo"].isoformat()
        datos.append(d)

    return responder({
        "ventana_horas": horas,
        "eventos_en_la_ventana": total,
        "no_exitosos": sum(d["n"] for d in datos),
        "por_accion_y_resultado": datos,
        "nota": "Un rechazo NO es una falla del sistema. "
                "RECHAZADO_PERMISO es el control funcionando, y "
                "GRUPO_INSUFICIENTE es la privacidad diferencial haciendo "
                "su trabajo. Lo que hay que mirar aqui es un cambio "
                "brusco en el volumen, no el volumen en si.",
    }, 200, raiz="errores_respuesta")


# =========================================================================
# Supervisión de contenedores: los reinicios
# =========================================================================
# POR QUÉ ESTO NO ES LO MISMO QUE LA SONDA DE SALUD
# --------------------------------------------------
# Un contenedor que se reinicia en bucle pasa TODAS las sondas. Cada
# petición llega a un proceso recién arrancado que contesta «vivo» con
# toda honestidad, así que el panel de componentes lo muestra en verde
# mientras el servicio pierde cada petición en vuelo, cada conexión del
# pool y cada caché caliente.
#
# Esta es la única vista del proyecto donde ese problema se ve.
#
# POR QUÉ NO SE LEE EL SOCKET DE DOCKER
# --------------------------------------
# Sería lo directo —`docker ps` dice los reinicios— y se decidió no
# hacerlo. Montar `/var/run/docker.sock` dentro de un contenedor le da
# control del demonio de Docker al proceso que lo monta, y con eso puede
# arrancar otro contenedor con el sistema de archivos del anfitrión
# montado. Es equivalente a darle root en la máquina. Un panel de
# monitoreo no vale eso, y además el proyecto tiene que funcionar también
# sin Docker, que es como corre la demostración cuando no hay acceso a
# Docker Hub.
#
# En su lugar se compara la IDENTIDAD de instancia que cada servicio
# reporta en `/health/live`: un identificador nuevo significa un proceso
# nuevo, es decir un reinicio. Funciona dentro y fuera de Docker, y no
# pide ningún privilegio.
VENTANA_REINICIOS = int(os.environ.get("MONITOREO_VENTANA_REINICIOS", "3600"))
REINICIOS_EN_BUCLE = int(os.environ.get("MONITOREO_REINICIOS_BUCLE", "3"))

# El estado vive en Redis y no en memoria del proceso. Si viviera en
# memoria, el conteo de reinicios se perdería cada vez que ESTE servicio
# se reiniciara, que es justo cuando se está investigando algo.
CLAVE_INSTANCIAS = "monitoreo:instancias"
CLAVE_REINICIOS = "monitoreo:reinicios"


def _vida_de(nombre, puerto):
    """Lee `/health/live` de un componente. Nunca lanza."""
    import json
    url = _url_de(nombre, puerto).replace("/health/ready", "/health/live")
    try:
        with urllib.request.urlopen(url, timeout=ESPERA_SEGUNDOS) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except Exception:
        return None


def _registrar_instancia(nombre, instancia, arrancado_en):
    """Guarda la instancia vista y anota el reinicio si cambió.

    Devuelve (reinicio_detectado, reinicios_en_la_ventana).
    """
    r = obtener_redis()
    anterior = r.hget(CLAVE_INSTANCIAS, nombre)
    if isinstance(anterior, bytes):
        anterior = anterior.decode("utf-8")

    reinicio = bool(anterior) and anterior != instancia
    r.hset(CLAVE_INSTANCIAS, nombre, instancia)

    clave = f"{CLAVE_REINICIOS}:{nombre}"
    ahora = time.time()
    if reinicio:
        r.zadd(clave, {f"{instancia}:{ahora}": ahora})
        # La ventana se recorta en cada escritura: sin esto, la clave
        # crece para siempre con reinicios de hace meses.
        r.zremrangebyscore(clave, 0, ahora - VENTANA_REINICIOS)
        r.expire(clave, VENTANA_REINICIOS * 2)
        _bitacora_monitoreo("COMPONENTE_REINICIADO", nombre, arrancado_en)
    cuantos = r.zcount(clave, ahora - VENTANA_REINICIOS, ahora)
    return reinicio, int(cuantos)


def _bitacora_monitoreo(accion, recurso, detalle):
    """Un reinicio tiene que quedar escrito donde no se borre.

    Redis recorta su propia ventana, así que sin este registro un bucle de
    reinicios de ayer no se puede reconstruir hoy.
    """
    try:
        with cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO auditoria.bitacora (actor_usuario_id, "
                " actor_perfil, accion, tipo_recurso, recurso_id, resultado, "
                " correlacion_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                ((g.get("actor") or {}).get("sub"),
                 ((g.get("actor") or {}).get("perfil") or "ANONIMO")[:30],
                 accion, "COMPONENTE", recurso[:60], "DETECTADO",
                 getattr(g, "correlacion_id", "")))
    except Exception:
        app.logger.exception("No se pudo registrar %s de %s", accion, recurso)


@app.get(f"{BASE}/contenedores")
@requiere_token
def contenedores():
    """Supervisión de los procesos: cuánto llevan arriba y si se reiniciaron.

    Es la vista que un panel de salud no puede dar. Un contenedor en bucle
    de reinicio contesta «vivo» en cada sonda, porque cada sonda le llega a
    un proceso nuevo.
    """
    limite_consumo(maximo=120)
    filas = []
    with futuros.ThreadPoolExecutor(max_workers=len(COMPONENTES)) as piscina:
        vidas = list(piscina.map(lambda c: (c[0], _vida_de(*c)), COMPONENTES))

    for nombre, vida in vidas:
        if not vida:
            filas.append({
                "componente": nombre, "responde": False,
                "nota": "No contesto la sonda de vida. Si el panel de "
                        "componentes lo muestra arriba, revisa primero la "
                        "red entre este contenedor y ese."})
            continue

        instancia = vida.get("instancia")
        if not instancia:
            # Un servicio con la biblioteca vieja. Se dice en lugar de
            # contarlo como «sin reinicios», que seria afirmar algo que no
            # se comprobo.
            filas.append({
                "componente": nombre, "responde": True,
                "segundos_arriba": vida.get("segundos_arriba"),
                "supervision": "NO_DISPONIBLE",
                "nota": "Este servicio no reporta identidad de instancia, "
                        "asi que no se puede saber si se reinicio. No "
                        "significa que no lo haya hecho."})
            continue

        reinicio, cuantos = _registrar_instancia(
            nombre, instancia, vida.get("arrancado_en") or "")
        arriba = vida.get("segundos_arriba") or 0
        fila = {
            "componente": nombre,
            "responde": True,
            "instancia": instancia,
            "arrancado_en": vida.get("arrancado_en"),
            "segundos_arriba": arriba,
            "reinicio_desde_la_ultima_revision": reinicio,
            "reinicios_en_la_ventana": cuantos,
            "ventana_segundos": VENTANA_REINICIOS,
            "en_bucle": cuantos >= REINICIOS_EN_BUCLE,
        }
        if fila["en_bucle"]:
            fila["nota"] = (
                f"{cuantos} reinicios en {VENTANA_REINICIOS // 60} minutos. "
                f"Las sondas de salud NO ven esto: cada una le llega a un "
                f"proceso recien arrancado y contesta que esta bien.")
        elif arriba and arriba < 60:
            fila["nota"] = ("Lleva menos de un minuto arriba. Puede ser un "
                            "despliegue normal o el inicio de un bucle; "
                            "vuelve a mirar en unos minutos.")
        filas.append(fila)

    en_bucle = [f["componente"] for f in filas if f.get("en_bucle")]
    return responder({
        "momento": dt.datetime.now(dt.timezone.utc).isoformat(),
        "total": len(filas),
        "en_bucle": en_bucle,
        "componentes": sorted(filas, key=lambda f: f["componente"]),
        "como_se_supervisa":
            "Comparando la identidad de instancia que cada servicio reporta "
            "en /health/live. Un identificador distinto significa un proceso "
            "nuevo, es decir un reinicio.",
        "por_que_no_se_lee_docker":
            "Montar el socket de Docker dentro de un contenedor le da "
            "control del demonio, y con eso puede arrancar otro contenedor "
            "con el sistema de archivos del anfitrion montado: equivale a "
            "root en la maquina. Un panel de monitoreo no vale eso. Y el "
            "proyecto tiene que funcionar tambien sin Docker, que es como "
            "corre la demostracion cuando no hay acceso a Docker Hub.",
    }, 200, raiz="contenedores_respuesta")


# =========================================================================
# Alertas
# =========================================================================
# POR QUÉ ESTE SERVICIO NO MANDA LAS ALERTAS, SOLO LAS PUBLICA
# -------------------------------------------------------------
# Mandarlas exigiría credenciales de correo o de mensajería dentro de este
# contenedor, y una cola propia para los reintentos. Un monitor cuyo envío
# falla en silencio es peor que no tener monitor: nadie se enteraría de
# nada y todos creerían estar cubiertos.
#
# La entrega de mensajes ya la hace notifications-service, que tiene su
# bandeja, sus preferencias y su registro. Duplicar eso aquí daría dos
# caminos que pueden decir cosas distintas.
#
# Así que las reglas se evalúan aquí y las alertas activas se publican con
# su severidad, su evidencia y qué hacer. Quien las entrega es otro.
SEVERIDADES = ("CRITICA", "ALTA", "MEDIA")


@app.get(f"{BASE}/alertas")
@requiere_token
def alertas():
    """Las alertas activas, evaluadas sobre el estado de ahora.

    Cada una lleva su evidencia y la acción que toca, porque una alerta
    que solo dice «algo va mal» obliga a reconstruir el diagnóstico cada
    vez.
    """
    limite_consumo(maximo=120)
    activas = []
    sondas = _sondear_todos()

    # --- Regla 1: un componente que no contesta ---
    for fila in sondas:
        if fila["estado"] == "sin_respuesta":
            activas.append({
                "regla": "COMPONENTE_SIN_RESPUESTA",
                "severidad": "CRITICA",
                "componente": fila["componente"],
                "evidencia": fila.get("error") or "no contesto la sonda",
                "accion": "Revisa el proceso y sus bitacoras. Si el "
                          "componente es esencial para una pantalla, esa "
                          "pantalla esta caida ahora mismo."})
        elif fila["estado"] == "no_listo":
            activas.append({
                "regla": "COMPONENTE_NO_LISTO",
                "severidad": "ALTA",
                "componente": fila["componente"],
                "evidencia": f"le falta: {', '.join(fila.get('falta') or [])}",
                "accion": "El servicio esta vivo y le falta una dependencia "
                          "esencial. Atiende la dependencia, no el servicio."})
        elif fila["estado"] == "degradado":
            activas.append({
                "regla": "COMPONENTE_DEGRADADO",
                "severidad": "MEDIA",
                "componente": fila["componente"],
                "evidencia": f"atiende sin: "
                             f"{', '.join(fila.get('degradado_por') or [])}",
                "accion": "No es urgente: el servicio atiende. Se reporta "
                          "para que no se vuelva permanente sin que nadie lo "
                          "decida."})
        if fila.get("latencia_alta"):
            activas.append({
                "regla": "LATENCIA_ALTA",
                "severidad": "MEDIA",
                "componente": fila["componente"],
                "evidencia": f"{fila['latencia_ms']} ms, por encima de "
                             f"{LATENCIA_ALTA_MS} ms",
                "accion": "Medida DESDE este contenedor en la red interna, "
                          "no es el tiempo que ve un usuario. Compara con "
                          "los demas componentes antes de concluir."})

    # --- Regla 2: una dependencia compartida esencial caída ---
    for nombre, prueba in (("postgresql", ping_pg), ("redis", _ping_redis)):
        try:
            prueba()
        except Exception as error:
            activas.append({
                "regla": "DEPENDENCIA_ESENCIAL_CAIDA",
                "severidad": "CRITICA",
                "componente": nombre,
                "evidencia": str(error)[:200],
                "accion": f"Los {len(COMPONENTES)} componentes dependen de "
                          f"{nombre}. Atiende esto antes que cualquier "
                          f"alerta de componente: casi todas vienen de aqui."})

    # --- Regla 3: contenedores en bucle de reinicio ---
    # Es la regla que justifica la vista de contenedores: sin ella, un
    # bucle de reinicios no dispara ninguna alerta porque todas las sondas
    # salen bien.
    try:
        r = obtener_redis()
        ahora = time.time()
        for nombre, _ in COMPONENTES:
            cuantos = int(r.zcount(f"{CLAVE_REINICIOS}:{nombre}",
                                   ahora - VENTANA_REINICIOS, ahora))
            if cuantos >= REINICIOS_EN_BUCLE:
                activas.append({
                    "regla": "REINICIOS_EN_BUCLE",
                    "severidad": "ALTA",
                    "componente": nombre,
                    "evidencia": f"{cuantos} reinicios en "
                                 f"{VENTANA_REINICIOS // 60} minutos",
                    "accion": "Las sondas de salud no ven esto. Revisa la "
                              "bitacora del contenedor: casi siempre es una "
                              "variable de ambiente faltante o una "
                              "dependencia que no estaba al arrancar."})
    except Exception as error:
        app.logger.error("No se pudo evaluar la regla de reinicios: %s", error)

    # --- Regla 4: presupuesto de privacidad por agotarse ---
    # Es la alerta más propia de este sistema y la que no se parece a nada
    # de un monitor genérico: cuando el épsilon de una campaña se agota, la
    # campaña deja de poder publicar. No es una caída —todo responde— y
    # para quien la opera se ve como que «ya no salen datos nuevos».
    try:
        for fila in consultar(
                "SELECT campania_id, count(*) AS unidades, "
                "       sum(CASE WHEN agotado THEN 1 ELSE 0 END) AS agotadas, "
                "       min(epsilon_restante) AS minimo_restante "
                "  FROM agregado.v_estado_presupuesto "
                " GROUP BY campania_id ORDER BY campania_id"):
            agotadas = int(fila["agotadas"] or 0)
            unidades = int(fila["unidades"] or 0)
            if agotadas:
                activas.append({
                    "regla": "PRESUPUESTO_AGOTADO",
                    "severidad": "ALTA",
                    "componente": f"campania {fila['campania_id']}",
                    "evidencia": f"{agotadas} de {unidades} unidades sin "
                                 f"epsilon restante",
                    "accion": "Esas unidades ya no pueden publicar nuevos "
                              "agregados en esta campania. No es una falla: "
                              "es el presupuesto de privacidad haciendo su "
                              "trabajo. Si hace falta mas, se decide y se "
                              "asienta; no se sube callando."})
            elif unidades and float(fila["minimo_restante"] or 0) <= 1.0:
                activas.append({
                    "regla": "PRESUPUESTO_POR_AGOTARSE",
                    "severidad": "MEDIA",
                    "componente": f"campania {fila['campania_id']}",
                    "evidencia": f"a la unidad mas consumida le quedan "
                                 f"{float(fila['minimo_restante']):.2f}",
                    "accion": "Avisa antes de que se agote: cuando se agota, "
                              "la unidad deja de publicar y eso se ve como "
                              "«ya no salen datos», no como un error."})
    except Exception as error:
        app.logger.error("No se pudo evaluar el presupuesto: %s", error)

    orden = {s: i for i, s in enumerate(SEVERIDADES)}
    activas.sort(key=lambda a: (orden.get(a["severidad"], 9), a["regla"]))
    conteo = {s: sum(1 for a in activas if a["severidad"] == s)
              for s in SEVERIDADES}

    return responder({
        "momento": dt.datetime.now(dt.timezone.utc).isoformat(),
        "total": len(activas),
        "por_severidad": conteo,
        "alertas": activas,
        "reglas_evaluadas": ["COMPONENTE_SIN_RESPUESTA", "COMPONENTE_NO_LISTO",
                             "COMPONENTE_DEGRADADO", "LATENCIA_ALTA",
                             "DEPENDENCIA_ESENCIAL_CAIDA",
                             "REINICIOS_EN_BUCLE", "PRESUPUESTO_AGOTADO",
                             "PRESUPUESTO_POR_AGOTARSE"],
        "quien_las_entrega":
            "Nadie desde aqui: este servicio las PUBLICA. Enviarlas exigiria "
            "credenciales de correo y una cola de reintentos dentro de este "
            "contenedor, y un monitor cuyo envio falla en silencio es peor "
            "que no tener monitor. La entrega de mensajes la hace "
            "notifications-service, que ya tiene bandeja, preferencias y "
            "registro.",
        "nota":
            "Un COMPONENTE_DEGRADADO y un PRESUPUESTO_AGOTADO no son fallas: "
            "el primero es un servicio atendiendo sin una dependencia "
            "opcional y el segundo es la privacidad diferencial funcionando. "
            "Se publican para que no se vuelvan permanentes sin que nadie lo "
            "decida.",
    }, 200, raiz="alertas_respuesta")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PUERTO", "8123")))
