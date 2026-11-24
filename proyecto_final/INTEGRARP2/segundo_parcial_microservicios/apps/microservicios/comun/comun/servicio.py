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
import logging
import os
import time
import uuid

from flask import Flask, Response, g, jsonify, request

from .errores import ErrorApi, quiere_xml, registrar_manejadores
from .xmlizar import a_xml

VERSION_API = "v1"


def responder(datos: dict, http: int = 200, raiz: str = "respuesta"):
    """Devuelve el mismo contenido en JSON o en XML, según lo pedido."""
    if quiere_xml():
        return Response(a_xml(datos, raiz=raiz), status=http,
                        mimetype="application/xml")
    return jsonify(datos), http


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
            raise ErrorApi("LIMITE_EXCEDIDO",
                           f"Mas de {maximo} peticiones por {ventana} segundos.", 429)
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
        return jsonify(servicio=nombre, estado="vivo", version=VERSION_API)

    @app.get("/health/ready")
    def _listo():
        detalle, ok = {}, True
        for etiqueta, fn in comprobaciones.items():
            t = time.perf_counter()
            try:
                fn()
                detalle[etiqueta] = {"ok": True,
                                     "ms": round((time.perf_counter() - t) * 1000, 1)}
            except Exception as e:
                ok = False
                detalle[etiqueta] = {"ok": False, "error": str(e)[:200]}
        return jsonify(servicio=nombre, estado="listo" if ok else "no_listo",
                       dependencias=detalle), (200 if ok else 503)

    @app.get("/health")
    def _salud():
        return jsonify(servicio=nombre, descripcion=descripcion,
                       version=VERSION_API, ambiente=ambiente)

    registrar_manejadores(app)
    return app
