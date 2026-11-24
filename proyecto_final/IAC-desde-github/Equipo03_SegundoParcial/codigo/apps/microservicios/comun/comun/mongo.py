"""
Acceso a MongoDB.

Dos reglas que este módulo hace cumplir y que no son negociables en este
proyecto:

1. NINGÚN documento puede contener `empleado_id`. La separación entre
   identidad y respuestas vive en PostgreSQL; si el identificador de
   empleado llegara a MongoDB, la seudonimización dejaría de existir en la
   práctica. La validación está aquí, en la capa de acceso, y no en cada
   endpoint: así no depende de que quien escriba el siguiente servicio se
   acuerde de la regla.

2. Los índices se declaran en el código y se crean al arrancar. Un índice
   que solo existe porque alguien lo creó a mano en su máquina desaparece
   en el siguiente despliegue.
"""
import os

from pymongo import ASCENDING, DESCENDING, MongoClient

from .errores import ErrorApi

# Campos que no pueden viajar a MongoDB bajo ninguna circunstancia.
CAMPOS_PROHIBIDOS = {"empleado_id", "numero_empleado", "curp", "rfc",
                     "nombre_empleado", "correo_empleado"}

_cliente = None


def obtener_cliente():
    global _cliente
    if _cliente is None:
        # El tiempo de seleccion debe ser MENOR que el que espera quien
        # consulta /health/ready. Si fuera mayor, un MongoDB caido haria
        # que la sonda no alcanzara a responder y el servicio se veria
        # "caido" en lugar de "degradado", que es informacion distinta
        # para quien opera el sistema.
        _cliente = MongoClient(
            os.environ.get("MONGO_URI", "mongodb://documentos:27017"),
            serverSelectionTimeoutMS=int(os.environ.get("MONGO_TIMEOUT_MS", "1200")),
            connectTimeoutMS=1200, tz_aware=True)
    return _cliente


def base():
    return obtener_cliente()[os.environ.get("MONGO_BASE", "bienestar")]


def ping():
    obtener_cliente().admin.command("ping")


def verificar_sin_identidad(doc: dict, ruta: str = ""):
    """Recorre el documento completo, incluidos los anidados."""
    for clave, valor in doc.items():
        completa = f"{ruta}.{clave}" if ruta else clave
        if clave.lower() in CAMPOS_PROHIBIDOS:
            raise ErrorApi(
                "CAMPO_PROHIBIDO",
                f"El campo '{completa}' no puede almacenarse en MongoDB: "
                f"rompe la separacion entre identidad y respuestas.", 422,
                [{"campo": completa, "problema": "identificador directo de persona"}])
        if isinstance(valor, dict):
            verificar_sin_identidad(valor, completa)
        elif isinstance(valor, (list, tuple)):
            for i, item in enumerate(valor):
                if isinstance(item, dict):
                    verificar_sin_identidad(item, f"{completa}[{i}]")


def asegurar_indices(definiciones: dict):
    """definiciones: {coleccion: [([(campo, orden), ...], {opciones}), ...]}"""
    db = base()
    creados = []
    for coleccion, indices in definiciones.items():
        for llaves, opciones in indices:
            nombre = db[coleccion].create_index(llaves, **opciones)
            creados.append(f"{coleccion}.{nombre}")
    return creados


__all__ = ["ASCENDING", "DESCENDING", "obtener_cliente", "base", "ping",
           "verificar_sin_identidad", "asegurar_indices", "CAMPOS_PROHIBIDOS"]
