"""
Sistema web de la Plataforma de Bienestar Laboral.

Es el núcleo administrativo y operativo: funciona de forma autónoma, sin
depender del módulo de microservicios ni de las aplicaciones cliente, que
corresponden a parciales posteriores.
"""
import logging
import time

from flask import Flask, g, jsonify, render_template, request

from .config import Config
from .datos import obtener_redis, cursor
from .seguridad import cargar_usuario

MENU = [
    # (etiqueta, endpoint, permisos que lo habilitan)
    ("Inicio",           "portal.inicio",          None),
    ("Notificaciones",   "notificaciones.bandeja", None),
    ("Mi consentimiento", "portal.consentimiento", ("CONSENT_OTORGAR",)),
    ("Mis accesos",      "portal.mis_accesos",     ("PARTICIPACION_PROPIA",)),
    ("Panel",            "panel.inicio",           ("AGREGADO_UNIDAD", "AGREGADO_GLOBAL")),
    ("Recomendaciones",  "panel.recomendaciones",  ("RECOMENDACION_CONSULTAR",)),
    ("Campañas",         "campanias.listar",       ("CAMPANIA_ADMIN",)),
    ("Intervenciones",   "intervenciones.listar",  ("INTERVENCION_PROPONER", "INTERVENCION_APROBAR",
                                                    "INTERVENCION_SEGUIMIENTO")),
    ("Evidencias",       "evidencias.listar",      ("INTERVENCION_SEGUIMIENTO",
                                                    "INTERVENCION_APROBAR",
                                                    "BITACORA_CONSULTAR")),
    ("Unidades",         "catalogos.unidades",     ("USUARIO_ADMIN", "CAMPANIA_ADMIN")),
    ("Instrumentos",     "catalogos.instrumentos", ("INSTRUMENTO_ADMIN",)),
    ("Reportes",         "reportes.listar",        ("AGREGADO_UNIDAD", "AGREGADO_GLOBAL",
                                                    "BITACORA_CONSULTAR", "PARAMETRO_ADMIN",
                                                    "RECOMENDACION_CONSULTAR",
                                                    "INTERVENCION_APROBAR",
                                                    "INTERVENCION_SEGUIMIENTO")),
    ("Bitácora",         "gobierno.bitacora",      ("BITACORA_CONSULTAR",)),
    ("Consentimientos",  "gobierno.consentimientos", ("CONSENT_EVIDENCIA_AUDIT",)),
    ("Garantías",        "gobierno.garantias",     ("BITACORA_CONSULTAR", "PARAMETRO_ADMIN")),
    ("Parámetros",       "gobierno.parametros",    ("PARAMETRO_ADMIN",)),
    ("Usuarios",         "administracion.usuarios", ("USUARIO_ADMIN",)),
    ("Perfiles",         "perfiles.listar",        ("USUARIO_ADMIN",)),
    ("Permisos",         "administracion.permisos", ("USUARIO_ADMIN", "BITACORA_CONSULTAR")),
    ("Servicios",        "administracion.servicios", ("PARAMETRO_ADMIN", "USUARIO_ADMIN")),
]


def crear_app() -> Flask:
    app = Flask(__name__,
                template_folder="../plantillas",
                static_folder="../estaticos",
                static_url_path="/estaticos")
    app.config["SECRET_KEY"] = Config.JWT_SECRETO  # solo para mensajes flash
    logging.basicConfig(
        level=getattr(logging, Config.NIVEL_BITACORA, logging.INFO),
        format="%(asctime)s %(levelname)s [" + Config.AMBIENTE + "] %(message)s")

    from .rutas import (administracion, campanias, catalogos, evidencias,
                        gobierno, intervenciones, notificaciones, panel,
                        perfiles, portal, publico, reportes, sesion)
    for bp in (publico.bp, sesion.bp, portal.bp, panel.bp, catalogos.bp,
               campanias.bp, intervenciones.bp, evidencias.bp, gobierno.bp,
               notificaciones.bp, reportes.bp, administracion.bp, perfiles.bp):
        app.register_blueprint(bp)

    # Tope del cuerpo de una peticion. Va aqui y no solo en la ruta de
    # carga: sin este limite, Flask lee en memoria todo lo que le manden
    # antes de que cualquier validacion llegue a ejecutarse, de modo que un
    # archivo de 2 GB tumbaria el proceso sin pasar por ninguna de las
    # comprobaciones de evidencias.py.
    import os as _os
    tope = int(_os.environ.get("EVIDENCIA_TAMANO_MAXIMO", str(8 * 1024 * 1024)))
    app.config["MAX_CONTENT_LENGTH"] = tope + 64 * 1024   # + encabezados

    @app.before_request
    def _antes():
        g.inicio = time.perf_counter()
        if request.path.startswith("/estaticos") or request.path.startswith("/salud"):
            g.sesion, g.permisos = None, set()
            return
        cargar_usuario()

    @app.after_request
    def _despues(resp):
        ms = (time.perf_counter() - getattr(g, "inicio", time.perf_counter())) * 1000
        if not request.path.startswith("/estaticos"):
            app.logger.info("%s %s -> %s en %.1f ms",
                            request.method, request.path, resp.status_code, ms)
        # Encabezados de seguridad. Se ponen aquí y también en el proxy:
        # si un día el sistema se sirve sin proxy, no se pierden.
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp

    @app.context_processor
    def _contexto():
        """Arma el menú según los permisos reales del perfil.

        Esconder una opción es comodidad, no seguridad: cada ruta vuelve a
        validar el permiso en el servidor.
        """
        permisos = g.get("permisos", set())
        visibles = [(t, e) for t, e, req in MENU
                    if req is None or (set(req) & permisos)]
        return dict(menu=visibles, sesion=g.get("sesion"),
                    permisos=permisos, ambiente=Config.AMBIENTE)

    # --------------------------------------------------- sondas de salud
    @app.get("/salud")
    def salud():
        return jsonify(estado="vivo", ambiente=Config.AMBIENTE)

    @app.get("/listo")
    def listo():
        detalle, ok = {}, True
        t = time.perf_counter()
        try:
            with cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            detalle["postgresql"] = {"ok": True, "ms": round((time.perf_counter()-t)*1000, 1)}
        except Exception as e:
            ok = False
            detalle["postgresql"] = {"ok": False, "error": _mensaje(e)}
        t = time.perf_counter()
        try:
            obtener_redis().ping()
            detalle["redis"] = {"ok": True, "ms": round((time.perf_counter()-t)*1000, 1)}
        except Exception as e:
            ok = False
            detalle["redis"] = {"ok": False, "error": _mensaje(e)}
        return jsonify(estado="listo" if ok else "no_listo",
                       ambiente=Config.AMBIENTE, dependencias=detalle), (200 if ok else 503)

    # ------------------------------------------------------------ errores
    @app.errorhandler(404)
    def _404(_):
        return render_template("error.html", codigo=404,
                               mensaje="La página que buscas no existe."), 404

    @app.errorhandler(403)
    def _403(_):
        return render_template("error.html", codigo=403,
                               mensaje="No tienes permiso para ver esto."), 403

    @app.errorhandler(500)
    def _500(e):
        app.logger.exception("Error no controlado")
        return render_template("error.html", codigo=500,
                               mensaje=_mensaje(e)), 500

    return app


def _mensaje(e) -> str:
    return str(e) if Config.MOSTRAR_ERRORES else \
        "Ocurrió un error en el servidor. El evento quedó registrado."
