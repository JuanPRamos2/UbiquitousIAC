"""
Manejo estandarizado de errores.

Todos los microservicios devuelven el MISMO sobre de error, en JSON o en
XML según lo que pida el cliente. Que la forma sea una sola es lo que
permite que la aplicación móvil y la de escritorio escriban su manejo de
errores una vez, en lugar de uno por servicio.

Forma del error:

    {
      "error": {
        "codigo": "SIN_PERMISO",
        "mensaje": "texto legible para una persona",
        "detalles": [ ... opcional ... ],
        "correlacion_id": "a1b2c3"
      }
    }

El codigo es estable y sirve para programar contra el; el mensaje puede
cambiar de redaccion sin romper a nadie.
"""
from flask import g, jsonify, request

from .xmlizar import a_xml


class ErrorApi(Exception):
    """Error previsto, con su código HTTP. No es una falla del servicio."""

    def __init__(self, codigo: str, mensaje: str, http: int = 400, detalles=None):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.http = http
        self.detalles = detalles or []


def cuerpo_error(codigo, mensaje, detalles=None):
    return {"error": {
        "codigo": codigo,
        "mensaje": mensaje,
        "detalles": detalles or [],
        "correlacion_id": getattr(g, "correlacion_id", ""),
    }}


def responder_error(codigo, mensaje, http, detalles=None):
    cuerpo = cuerpo_error(codigo, mensaje, detalles)
    if quiere_xml():
        return a_xml(cuerpo, raiz="error_respuesta"), http, \
               {"Content-Type": "application/xml; charset=utf-8"}
    return jsonify(cuerpo), http


def quiere_xml() -> bool:
    """El formato se decide por Accept, o por ?formato=xml para probar desde el navegador."""
    if request.args.get("formato", "").lower() == "xml":
        return True
    accept = request.headers.get("Accept", "")
    return "xml" in accept.lower() and "json" not in accept.lower()


def registrar_manejadores(app):
    @app.errorhandler(ErrorApi)
    def _api(e):
        return responder_error(e.codigo, e.mensaje, e.http, e.detalles)

    @app.errorhandler(404)
    def _404(_):
        return responder_error(
            "RECURSO_NO_ENCONTRADO",
            "La ruta solicitada no existe en este servicio.", 404)

    @app.errorhandler(405)
    def _405(_):
        return responder_error(
            "METODO_NO_PERMITIDO",
            "El metodo HTTP no esta permitido en esta ruta.", 405)

    @app.errorhandler(Exception)
    def _500(e):
        app.logger.exception("Error no controlado")
        # Fuera de developer no se devuelve el detalle: el rastro de una
        # excepcion puede revelar la estructura interna del sistema.
        import os
        detalle = str(e) if os.environ.get("MOSTRAR_ERRORES") == "true" else \
            "Error interno del servicio. El evento quedo registrado."
        return responder_error("ERROR_INTERNO", detalle, 500)
