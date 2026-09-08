import logging
from pathlib import Path

from flask import Flask, Response, request

from config import settings
from soap.envelope import body_operation, parse_envelope
from soap.faults import SoapFault, client_fault, server_fault
from soap.service import handle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("library_soap")

app = Flask(__name__)
WSDL_TEXT = Path(settings.WSDL_PATH).read_text(encoding="utf-8")


def _wsdl_for_request():
    location = request.url_root.rstrip("/") + "/soap"
    return WSDL_TEXT.replace("http://localhost:5000/soap", location)


@app.get("/")
def index():
    return {
        "service": "LibraryClassifier",
        "wsdl": "/soap?wsdl",
        "endpoint": "/soap",
    }


@app.get("/soap")
@app.get("/wsdl")
def wsdl():
    return Response(_wsdl_for_request(), mimetype="text/xml; charset=utf-8")


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


if __name__ == "__main__":
    app.run(host=settings.SOAP_HOST, port=settings.SOAP_PORT, debug=False)
