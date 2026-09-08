import logging
import re
from pathlib import Path

from flask import Flask, Response, request, send_from_directory

from books_api import register_books_routes
from config import settings
from soap.envelope import body_operation, parse_envelope
from soap.faults import SoapFault, client_fault, server_fault
from soap.service import handle
from xml_format import respond, wants_json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("library_soap")

app = Flask(__name__)
try:
    from flask_cors import CORS

    CORS(app)
except ImportError:
    pass

SOAP_DIR = Path(__file__).resolve().parent


def repo_root():
    for candidate in (SOAP_DIR, *SOAP_DIR.parents):
        if (candidate / "ejercicio02").is_dir() and (candidate / "ejercicio03").is_dir():
            return candidate
    return SOAP_DIR.parents[2]


REPO_ROOT = repo_root()
EG3_DIR = REPO_ROOT / "ejercicio03"
SITE_DIR = REPO_ROOT
COVERS_DIR = SOAP_DIR / "static" / "covers"
COVERS_FALLBACK = REPO_ROOT / "ejercicio02" / "html" / "img" / "covers"
WSDL_TEXT = Path(settings.WSDL_PATH).read_text(encoding="utf-8")


def _wsdl_for_request():
    location = request.url_root.rstrip("/") + "/soap"
    return WSDL_TEXT.replace("http://localhost:5000/soap", location)


def _probar_html():
    html = (EG3_DIR / "probar.html").read_text(encoding="utf-8")
    html = html.replace('href="../style.css"', 'href="/site-style.css"')
    html = html.replace('src="../js/site.js"', 'src="/site-js.js"')
    html = html.replace("../index.html", "/")
    html = html.replace("<body>", '<body data-soap-endpoint="/soap">')
    return html


def _covers_dir():
    if COVERS_DIR.exists():
        return COVERS_DIR
    return COVERS_FALLBACK


def _service_descriptor():
    return {
        "service": "LibraryClassifier",
        "library": "Ejercicio guiado 02",
        "wsdl": "/soap?wsdl",
        "endpoint": "/soap",
        "demo": settings.SOAP_DEMO,
        "defaultFormat": "xml",
        "jsonParameter": "format=json",
        "endpoints": [
            {"path": "/books", "methods": "GET", "description": "Catálogo completo de la librería"},
            {
                "path": "/books/9780451524935",
                "methods": "GET",
                "description": "Un libro por ISBN (ejemplo: 1984)",
            },
            {
                "path": "/cloud-concepts",
                "methods": "GET",
                "description": "IaaS, PaaS, SaaS y FaaS con los libros del catálogo",
            },
            {
                "path": "/books-images",
                "methods": "GET",
                "description": "Datos mínimos de cada libro con su portada",
            },
            {"path": "/soap", "methods": "GET, POST", "description": "WSDL (GET) y operaciones SOAP (POST)"},
            {"path": "/covers/<isbn>.svg", "methods": "GET", "description": "Imagen de portada"},
        ],
    }


@app.get("/")
def index():
    if wants_json() or (request.args.get("format") or "").strip().lower() == "xml":
        return respond(_service_descriptor(), root_tag="service")
    if (EG3_DIR / "probar.html").exists():
        return Response(_probar_html(), mimetype="text/html; charset=utf-8")
    return respond(_service_descriptor(), root_tag="service")


@app.get("/probar.html")
def probar():
    return Response(_probar_html(), mimetype="text/html; charset=utf-8")


@app.get("/site-style.css")
def site_style():
    return send_from_directory(SITE_DIR, "style.css")


@app.get("/site-js.js")
def site_js():
    return send_from_directory(SITE_DIR / "js", "site.js")


@app.get("/css/<path:filename>")
def eg3_css(filename):
    return send_from_directory(EG3_DIR / "css", filename)


@app.get("/js/<path:filename>")
def eg3_js(filename):
    return send_from_directory(EG3_DIR / "js", filename)


@app.get("/covers/<path:filename>")
def cover_file(filename):
    match = re.search(r"(\d{10,13})", filename)
    if match:
        svg_name = f"{match.group(1)}.svg"
        directory = _covers_dir()
        if (directory / svg_name).exists():
            return send_from_directory(directory, svg_name)
    directory = _covers_dir()
    return send_from_directory(directory, filename)


@app.get("/soap")
@app.get("/wsdl")
def wsdl():
    if wants_json():
        return respond(
            {
                "format": "json",
                "wsdl": "/soap?wsdl",
                "location": request.url_root.rstrip("/") + "/soap",
                "operations": [
                    "ObtenerConceptosPendientes",
                    "RegistrarClasificacion",
                    "ObtenerProgresoUsuario",
                    "ObtenerEstadisticasPorModelo",
                ],
            },
            root_tag="soapInfo",
        )
    return Response(_wsdl_for_request(), mimetype="text/xml; charset=utf-8")


@app.post("/demo/reset")
def demo_reset():
    if not settings.SOAP_DEMO:
        return respond({"error": "Not found"}, root_tag="error", status=404)
    from db.demo_store import reset

    reset()
    return respond({"ok": True}, root_tag="result")


@app.post("/soap")
def soap_endpoint():
    raw = request.get_data()
    if not raw:
        fault = client_fault("El cuerpo HTTP está vacío")
        return Response(fault.to_xml(), status=fault.http_status, mimetype="text/xml; charset=utf-8")
    try:
        _root, header, body = parse_envelope(raw)
        payload = body_operation(body)
        if payload is None:
            raise client_fault("El Body SOAP no contiene una operación")
        xml = handle(header, payload)
        return Response(xml, status=200, mimetype="text/xml; charset=utf-8")
    except SoapFault as fault:
        return Response(fault.to_xml(), status=fault.http_status, mimetype="text/xml; charset=utf-8")
    except ValueError as exc:
        fault = client_fault(str(exc))
        return Response(fault.to_xml(), status=fault.http_status, mimetype="text/xml; charset=utf-8")
    except Exception:
        logger.exception("Error no controlado en el endpoint SOAP")
        fault = server_fault()
        return Response(fault.to_xml(), status=fault.http_status, mimetype="text/xml; charset=utf-8")


register_books_routes(app)


if __name__ == "__main__":
    app.run(host=settings.SOAP_HOST, port=settings.SOAP_PORT, debug=False)
