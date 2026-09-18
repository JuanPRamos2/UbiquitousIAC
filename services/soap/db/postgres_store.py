from db.connection import execute_in_transaction, fetch_all, fetch_one
from db.errors import (
    ConceptNotFoundError,
    DatabaseError,
    DuplicateClassificationError,
    InvalidModelError,
)


def _pg_code(exc):
    return getattr(exc, "pgcode", None) or ""


def _pg_message(exc):
    return str(getattr(exc, "pgerror", None) or exc)


def obtener_conceptos_pendientes(correo):
    try:
        return fetch_all("SELECT * FROM sp_obtener_conceptos_pendientes(%s)", (correo,))
    except Exception as exc:
        raise DatabaseError("No se pudieron consultar los conceptos pendientes") from exc


def registrar_clasificacion(nombre, apellidos, correo, concept_id, isbn, modelo, tipo_cliente):
    def _run(cur):
        cur.execute(
            "SELECT sp_registrar_clasificacion(%s, %s, %s, %s, %s, %s, %s) AS id",
            (nombre, apellidos, correo, concept_id, isbn, modelo, tipo_cliente),
        )
        row = cur.fetchone()
        return int(row["id"])

    try:
        return execute_in_transaction(_run)
    except Exception as exc:
        message = _pg_message(exc)
        code = _pg_code(exc)
        if "CLASIFICACION_DUPLICADA" in message or code == "23505":
            raise DuplicateClassificationError("El concepto ya fue clasificado por este usuario") from exc
        if "CONCEPTO_INEXISTENTE" in message or code == "P0002":
            raise ConceptNotFoundError("El concepto no existe en el catálogo de la librería") from exc
        if "MODELO_INVALIDO" in message or code == "22023":
            raise InvalidModelError("El modelo debe ser IaaS, PaaS, SaaS o FaaS") from exc
        raise DatabaseError("No se pudo registrar la clasificación") from exc


def obtener_progreso_usuario(correo):
    try:
        row = fetch_one("SELECT * FROM sp_obtener_progreso_usuario(%s)", (correo,))
        return row or {}
    except Exception as exc:
        raise DatabaseError("No se pudo consultar el progreso del usuario") from exc


def obtener_estadisticas_por_modelo():
    try:
        return fetch_all("SELECT * FROM sp_obtener_estadisticas_por_modelo()")
    except Exception as exc:
        raise DatabaseError("No se pudieron consultar las estadísticas") from exc


def registrar_cliente_consulta(tipo_cliente, identificador):
    def _run(cur):
        cur.execute(
            "SELECT sp_registrar_cliente_servido(%s, %s)",
            (tipo_cliente, identificador),
        )

    try:
        execute_in_transaction(_run)
    except Exception as exc:
        raise DatabaseError("No se pudo registrar el cliente atendido") from exc
