import logging
import re
from datetime import datetime, timezone

from config.settings import ALLOWED_MODELS
from db import repository
from xml.etree import ElementTree as ET

from config.settings import TNS
from soap.envelope import build_response, local_name, text_of
from soap.faults import SoapFault, client_fault, duplicate_fault, server_fault
from soap.security import require_username_token

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PROTECTED_OPERATIONS = {"ObtenerEstadisticasPorModelo"}


def _el(parent, tag, text=None):
    node = ET.SubElement(parent, f"{{{TNS}}}{tag}")
    if text is not None:
        node.text = str(text)
    return node


def _require(payload, field):
    value = text_of(payload, field)
    if not value:
        raise client_fault(f"El campo {field} es obligatorio")
    return value


def _require_email(payload):
    correo = _require(payload, "correo").lower()
    if not EMAIL_RE.match(correo):
        raise client_fault("El correo no tiene un formato válido")
    return correo


def _require_int(payload, field):
    raw = _require(payload, field)
    try:
        return int(raw)
    except ValueError as exc:
        raise client_fault(f"El campo {field} debe ser un entero") from exc


def handle(header, payload):
    operation = local_name(payload.tag)
    if operation in PROTECTED_OPERATIONS:
        require_username_token(header)
    handlers = {
        "ObtenerConceptosPendientes": obtener_conceptos_pendientes,
        "RegistrarClasificacion": registrar_clasificacion,
        "ObtenerProgresoUsuario": obtener_progreso_usuario,
        "ObtenerEstadisticasPorModelo": obtener_estadisticas_por_modelo,
    }
    handler = handlers.get(operation)
    if handler is None:
        raise client_fault(f"Operación no soportada: {operation}")
    try:
        return handler(payload)
    except SoapFault:
        raise
    except repository.DuplicateClassificationError as exc:
        raise duplicate_fault() from exc
    except repository.ConceptNotFoundError as exc:
        raise client_fault(str(exc), 404, "NotFoundFault") from exc
    except repository.InvalidModelError as exc:
        raise client_fault(str(exc), 400, "ValidationFault") from exc
    except repository.DatabaseError as exc:
        logger.exception("Error de persistencia")
        raise server_fault() from exc


def obtener_conceptos_pendientes(payload):
    correo = _require_email(payload)
    tipo_cliente = text_of(payload, "tipoCliente", "desktop-java") or "desktop-java"
    rows = repository.obtener_conceptos_pendientes(correo)
    repository.registrar_cliente_consulta(tipo_cliente, correo)

    def extra(response):
        for row in rows:
            item = _el(response, "concepto")
            _el(item, "conceptId", row["concept_id"])
            _el(item, "conceptName", row["concept_name"])
            _el(item, "definition", row["definition"])
            _el(item, "isbn", row["isbn"])
            _el(item, "bookTitle", row["book_title"])
            _el(item, "categoryName", row["category_name"])

    return build_response("ObtenerConceptosPendientes", [("total", len(rows))], extra)


def registrar_clasificacion(payload):
    nombre = _require(payload, "nombre")
    apellidos = _require(payload, "apellidos")
    correo = _require_email(payload)
    concept_id = _require_int(payload, "conceptId")
    isbn = _require(payload, "isbn")
    modelo = _require(payload, "modelo")
    tipo_cliente = _require(payload, "tipoCliente")

    if modelo not in ALLOWED_MODELS:
        raise client_fault("El modelo debe ser IaaS, PaaS, SaaS o FaaS", 400, "ValidationFault")

    clasificacion_id = repository.registrar_clasificacion(
        nombre, apellidos, correo, concept_id, isbn, modelo, tipo_cliente
    )
    fecha = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return build_response(
        "RegistrarClasificacion",
        [
            ("clasificacionId", clasificacion_id),
            ("mensaje", "Clasificación registrada"),
            ("modelo", modelo),
            ("fecha", fecha),
        ],
    )


def obtener_progreso_usuario(payload):
    correo = _require_email(payload)
    row = repository.obtener_progreso_usuario(correo)
    return build_response(
        "ObtenerProgresoUsuario",
        [
            ("correo", row.get("correo") or correo),
            ("nombreCompleto", row.get("nombre_completo") or "Sin registros"),
            ("clasificados", row.get("clasificados") or 0),
            ("pendientes", row.get("pendientes") or 0),
            ("totalCatalogo", row.get("total_catalogo") or 0),
        ],
    )


def obtener_estadisticas_por_modelo(_payload):
    rows = repository.obtener_estadisticas_por_modelo()

    def extra(response):
        for row in rows:
            item = _el(response, "item")
            _el(item, "modelo", row["modelo"])
            _el(item, "cantidad", row["cantidad"])

    return build_response("ObtenerEstadisticasPorModelo", [], extra)
