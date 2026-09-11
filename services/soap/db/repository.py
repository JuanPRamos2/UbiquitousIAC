from db.errors import (
    ConceptNotFoundError,
    DatabaseError,
    DuplicateClassificationError,
    InvalidModelError,
)

from config import settings

__all__ = [
    "ConceptNotFoundError",
    "DatabaseError",
    "DuplicateClassificationError",
    "InvalidModelError",
    "obtener_conceptos_pendientes",
    "obtener_estadisticas_por_modelo",
    "obtener_progreso_usuario",
    "registrar_clasificacion",
    "registrar_cliente_consulta",
]


def _impl():
    if settings.SOAP_DEMO:
        from db import demo_store as store
    else:
        from db import postgres_store as store
    return store


def obtener_conceptos_pendientes(correo):
    return _impl().obtener_conceptos_pendientes(correo)


def registrar_clasificacion(nombre, apellidos, correo, concept_id, isbn, modelo, tipo_cliente):
    return _impl().registrar_clasificacion(
        nombre, apellidos, correo, concept_id, isbn, modelo, tipo_cliente
    )


def obtener_progreso_usuario(correo):
    return _impl().obtener_progreso_usuario(correo)


def obtener_estadisticas_por_modelo():
    return _impl().obtener_estadisticas_por_modelo()


def registrar_cliente_consulta(tipo_cliente, identificador):
    return _impl().registrar_cliente_consulta(tipo_cliente, identificador)
