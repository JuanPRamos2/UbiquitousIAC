"""
Fábrica común de microservicios.

Todo servicio del proyecto obtiene de aquí, sin volver a escribirlo:

  - identificador de correlación por petición, que viaja en la respuesta
    y en la bitácora, para poder seguir una operación que atraviesa varios
    servicios;
  - registro de actividad de cada petición;
  - los tres endpoints de salud que pide la rúbrica;
  - manejo estandarizado de errores;
  - respuesta en JSON o XML según el encabezado Accept;
  - límite de consumo por token, apoyado en Redis.

Lo que NO está aquí es la lógica de negocio: cada servicio tiene una sola
responsabilidad y la implementa en su propio archivo.
"""
import datetime
import logging
import os
import time
import uuid

from flask import Flask, Response, g, jsonify, request

from .errores import ErrorApi, quiere_xml, registrar_manejadores
from .xmlizar import a_xml

VERSION_API = "v1"

# La identidad de este proceso. Se calcula una vez, al importar el módulo,
# y es lo que permite a monitoring-service distinguir «el servicio sigue
# arriba» de «el servicio se reinició y ahora está arriba otra vez». Las
# dos cosas se ven idénticas desde una sonda de vida sin esto.
_INICIO = time.time()
INSTANCIA = uuid.uuid4().hex[:12]
ARRANCADO_EN = datetime.datetime.fromtimestamp(
    _INICIO, datetime.timezone.utc).isoformat()


def responder(datos: dict, http: int = 200, raiz: str = "respuesta"):
    """Devuelve el mismo contenido en JSON o en XML, según lo pedido.

    Siempre se devuelve un objeto Response, no la tupla (cuerpo, codigo).
    La diferencia importa porque un endpoint que necesita agregar una
    cabecera —X-Cache en queries-service, X-Reporte-Sello en
    reports-service— puede hacerlo sobre lo que esta funcion devuelve, en
    lugar de tener que rearmar la respuesta a mano y arriesgarse a que la
    version XML y la JSON salgan distintas.
    """
    if quiere_xml():
        return Response(a_xml(datos, raiz=raiz), status=http,
                        mimetype="application/xml")
    respuesta = jsonify(datos)
    respuesta.status_code = http
    return respuesta


def pagina():
    """Lee y valida los parámetros de paginación.

    El tope de 100 por página no es decorativo: sin él, un cliente podría
    pedir un millón de registros y tumbar el servicio con una sola
    petición.
    """
    try:
        p = int(request.args.get("pagina", 1))
        t = int(request.args.get("tamano", 20))
    except ValueError:
        raise ErrorApi("PARAMETRO_INVALIDO",
                       "Los parametros 'pagina' y 'tamano' deben ser enteros.", 400)
    if p < 1:
        raise ErrorApi("PARAMETRO_INVALIDO", "'pagina' empieza en 1.", 400)
    if not 1 <= t <= 100:
        raise ErrorApi("PARAMETRO_INVALIDO",
                       "'tamano' debe estar entre 1 y 100.", 400)
    return p, t


def sobre_pagina(elementos, total, p, t, clave="elementos"):
    """Sobre de paginación común a todos los listados."""
    total_paginas = max(1, (total + t - 1) // t)
    return {
        clave: elementos,
        "paginacion": {
            "pagina": p, "tamano": t, "total": total,
            "total_paginas": total_paginas,
            "tiene_siguiente": p < total_paginas,
            "tiene_anterior": p > 1,
        },
    }


def limite_consumo(maximo: int = 120, ventana: int = 60):
    """Límite de peticiones por token y minuto, con contador en Redis.

    Si Redis no responde, se deja pasar: el límite protege de un abuso,
    no de un ataque, y perder el límite es preferible a negar servicio a
    todos los clientes legítimos por una caída de la caché.
    """
    from .seguridad import obtener_redis
    try:
        clave_actor = (getattr(g, "actor", {}) or {}).get("jti") or request.remote_addr
        clave = f"limite:{request.blueprint or 'api'}:{clave_actor}"
        r = obtener_redis()
        n = r.incr(clave)
        if n == 1:
            r.expire(clave, ventana)
        if n > maximo:
            # El Retry-After sale del TTL REAL de la clave, no de la ventana
            # declarada: a quien llega al limite en el segundo 55 le quedan
            # 5 segundos, no 60, y decirle 60 lo deja esperando de mas.
            restante = r.ttl(clave)
            if not isinstance(restante, int) or restante < 1:
                restante = ventana
            raise ErrorApi(
                "LIMITE_EXCEDIDO",
                f"Mas de {maximo} peticiones por {ventana} segundos. "
                f"Reintenta en {restante} s.", 429,
                cabeceras={"Retry-After": str(restante)})
    except ErrorApi:
        raise
    except Exception:
        pass


def crear_servicio(nombre: str, descripcion: str, comprobaciones=None) -> Flask:
    """comprobaciones: dict nombre -> función sin argumentos que lanza si falla."""
    app = Flask(nombre)
    ambiente = os.environ.get("APP_AMBIENTE", "developer")
    logging.basicConfig(
        level=getattr(logging, os.environ.get("NIVEL_BITACORA", "INFO"), logging.INFO),
        format=f"%(asctime)s %(levelname)s [{nombre}/{ambiente}] %(message)s")

    comprobaciones = comprobaciones or {}

    @app.before_request
    def _antes():
        g.inicio = time.perf_counter()
        # Si el cliente ya trae un identificador de correlacion se respeta:
        # asi una operacion que pasa por tres servicios se puede seguir
        # completa en la bitacora con un solo identificador.
        g.correlacion_id = (request.headers.get("X-Correlacion-Id")
                            or uuid.uuid4().hex[:16])

    @app.after_request
    def _despues(resp):
        ms = (time.perf_counter() - getattr(g, "inicio", time.perf_counter())) * 1000
        resp.headers["X-Correlacion-Id"] = getattr(g, "correlacion_id", "")
        resp.headers["X-Servicio"] = nombre
        resp.headers["X-Version-Api"] = VERSION_API
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        if not request.path.startswith("/health"):
            app.logger.info("%s %s -> %s en %.1f ms [corr=%s]",
                            request.method, request.path, resp.status_code, ms,
                            getattr(g, "correlacion_id", ""))
        return resp

    # ------------------------------------------------- endpoints de salud
    @app.get("/health/live")
    def _vivo():
        """La sonda de vida, con la identidad de ESTA instancia.

        POR QUÉ DEVUELVE `instancia` Y `arrancado_en`
        ---------------------------------------------
        Sin esos dos campos, un contenedor que se reinicia en bucle pasa
        TODAS las sondas. Cada petición llega a un proceso recién
        arrancado que contesta «vivo» con toda honestidad, y el reinicio
        —que es el problema— no se ve en ningún lado.

        `instancia` es un identificador nuevo por proceso, así que
        monitoring-service puede comparar el de ahora con el que vio antes
        y contar los reinicios. Se usa el identificador y no solo la hora
        porque un contenedor sin reloj sincronizado puede reportar horas
        que no avanzan, y entonces el conteo por hora falla justo donde
        hace falta.
        """
        return jsonify(servicio=nombre, estado="vivo", version=VERSION_API,
                       instancia=INSTANCIA, arrancado_en=ARRANCADO_EN,
                       segundos_arriba=round(time.time() - _INICIO, 1))

    @app.get("/health/ready")
    def _listo():
        """Sonda de listo, con dependencias esenciales y dependencias opcionales.

        POR QUÉ LA DISTINCIÓN
        ---------------------
        Antes toda dependencia caída daba «no_listo» y 503. El efecto era
        incorrecto en un caso real: algorithms-service lee los agregados de
        PostgreSQL y solo usa MongoDB para guardar el historial de corridas.
        Con MongoDB caído, el motor evalúa perfectamente y responde
        /reglas, /evaluar y /cobertura; sin embargo se declaraba no listo, y
        un orquestador deja de mandarle tráfico a un servicio no listo. Es
        decir: una pieza que funcionaba se sacaba de servicio.

        Ahora hay tres estados en lugar de dos:

          listo      todo responde                      -> 200
          degradado  falla solo una dependencia opcional -> 200
          no_listo   falla una dependencia esencial      -> 503

        «degradado» con 200 es deliberado: el servicio SÍ puede atender, y
        el campo `degradado_por` dice qué dejó de funcionar para que quien
        opera lo vea sin tener que leer bitácoras. Devolver 503 aquí
        esconderia un servicio sano; devolver 200 sin decir nada esconderia
        la falla.

        Una dependencia se declara opcional pasando la tupla
        (función, "opcional") en lugar de la función sola.
        """
        detalle = {}
        esenciales_mal, opcionales_mal = [], []
        for etiqueta, declaracion in comprobaciones.items():
            fn, opcional = declaracion, False
            if isinstance(declaracion, tuple):
                fn, modo = declaracion
                opcional = str(modo).lower() == "opcional"
            t = time.perf_counter()
            try:
                fn()
                detalle[etiqueta] = {"ok": True, "esencial": not opcional,
                                     "ms": round((time.perf_counter() - t) * 1000, 1)}
            except Exception as e:
                detalle[etiqueta] = {"ok": False, "esencial": not opcional,
                                     "error": str(e)[:200]}
                (opcionales_mal if opcional else esenciales_mal).append(etiqueta)

        if esenciales_mal:
            estado, codigo = "no_listo", 503
        elif opcionales_mal:
            estado, codigo = "degradado", 200
        else:
            estado, codigo = "listo", 200

        cuerpo = {"servicio": nombre, "estado": estado, "dependencias": detalle}
        if opcionales_mal:
            cuerpo["degradado_por"] = sorted(opcionales_mal)
        if esenciales_mal:
            cuerpo["falta"] = sorted(esenciales_mal)
        return jsonify(cuerpo), codigo

    @app.get("/health")
    def _salud():
        return jsonify(servicio=nombre, descripcion=descripcion,
                       version=VERSION_API, ambiente=ambiente)

    registrar_manejadores(app)
    return app


def cuerpo_peticion(silencioso: bool = True) -> dict:
    """Lee el cuerpo de la petición, venga en JSON o en XML.

    POR QUÉ ESTA FUNCIÓN EXISTE
    ---------------------------
    Los servicios leían el cuerpo con request.get_json(). El efecto era que
    una aplicación cliente que mandara XML recibía un 422 por «campos
    obligatorios» aunque los hubiera mandado todos: get_json() devolvía
    None y el servicio veía un cuerpo vacío. Como la aplicación de
    escritorio del proyecto consume exclusivamente XML, sin esto no podía
    hacer ninguna operación de escritura.

    El formato se decide por Content-Type y no por el contenido: adivinar
    mirando si el primer carácter es '{' o '<' funcionaría casi siempre, y
    el «casi» de un encabezado mal puesto terminaría en un error que nadie
    puede explicar.

    Un cuerpo XML mal formado produce 400 y no 500: es un error del
    cliente, y decírselo con el detalle del parser le permite corregirlo.
    """
    tipo = (request.content_type or "").split(";")[0].strip().lower()
    if tipo in ("application/xml", "text/xml"):
        from .xmlizar import de_xml
        crudo = request.get_data(as_text=True)
        if not crudo.strip():
            return {}
        try:
            datos = de_xml(crudo)
        except ValueError as e:
            raise ErrorApi("XML_MAL_FORMADO", str(e), 400)
        if not isinstance(datos, dict):
            raise ErrorApi(
                "XML_INESPERADO",
                "El elemento raiz del cuerpo tiene que contener los campos "
                "como elementos hijos.", 400)
        return datos
    datos = request.get_json(silent=silencioso) or {}
    return datos if isinstance(datos, dict) else {}
