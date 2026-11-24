"""
Genera los esquemas JSON a partir de los contratos OpenAPI.

Por qué generarlos y no escribirlos aparte: si el esquema JSON se escribe a
mano junto al OpenAPI, los dos se desincronizan en cuanto alguien cambia un
campo en uno solo. Aquí hay una sola fuente —el contrato que publica cada
servicio— y los archivos de contratos/json/ se derivan de ella.

    python3 contratos/generar_json.py

Produce un archivo por esquema, en JSON Schema draft 2020-12, con las
referencias internas reescritas para que cada archivo se valide solo.
"""
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(RAIZ, "contratos", "json")

SERVICIOS = {
    "auth-service": "svc_auth_gen",
    "users-service": "svc_users_gen",
    "documents-service": "svc_docs_gen",
    "notifications-service": "svc_notif_gen",
}


def cargar_contrato(servicio, alias):
    """Importa el servicio solo para leer su contrato, sin levantarlo."""
    import importlib.util
    carpeta = os.path.join(RAIZ, "apps", "microservicios", servicio)
    sys.path.insert(0, carpeta)
    try:
        spec = importlib.util.spec_from_file_location(alias,
                                                      os.path.join(carpeta, "app.py"))
        modulo = importlib.util.module_from_spec(spec)
        sys.modules[alias] = modulo
        spec.loader.exec_module(modulo)
        cliente = modulo.app.test_client()
        return cliente.get("/openapi.json").get_json()
    finally:
        sys.path.remove(carpeta)
        sys.modules.pop("contrato", None)


def convertir(nodo):
    """Traduce de OpenAPI 3.0 a JSON Schema 2020-12.

    Dos diferencias que importan:

      - Las referencias cambian de #/components/schemas/X a #/$defs/X,
        porque cada archivo generado se valida por si solo.
      - OpenAPI 3.0 expresa "puede venir sin dato" con nullable: true;
        JSON Schema lo expresa poniendo "null" entre los tipos. Sin esta
        traduccion, un campo nulo legitimo —por ejemplo un alcance
        organizacional que significa "toda la organizacion"— haria fallar
        la validacion.
    """
    if isinstance(nodo, dict):
        salida = {}
        for k, v in nodo.items():
            if k == "$ref" and isinstance(v, str) \
                    and v.startswith("#/components/schemas/"):
                salida[k] = "#/$defs/" + v.rsplit("/", 1)[1]
            elif k == "nullable":
                continue          # se resuelve mas abajo sobre 'type'
            else:
                salida[k] = convertir(v)
        if nodo.get("nullable") is True:
            tipo = salida.get("type")
            if isinstance(tipo, str):
                salida["type"] = [tipo, "null"]
            elif isinstance(tipo, list) and "null" not in tipo:
                salida["type"] = tipo + ["null"]
            elif tipo is None:
                salida.setdefault("type", ["null"])
        return salida
    if isinstance(nodo, list):
        return [convertir(x) for x in nodo]
    return nodo


# Nombre conservado por compatibilidad con llamadas previas.
reescribir_refs = convertir


def main():
    os.makedirs(SALIDA, exist_ok=True)
    # mongomock solo para poder importar los servicios que usan MongoDB.
    import mongomock
    import comun.mongo as m
    cliente = mongomock.MongoClient()
    m.obtener_cliente = lambda: cliente
    m.base = lambda: cliente["bienestar"]
    m.ping = lambda: None

    escritos = []
    for servicio, alias in SERVICIOS.items():
        contrato = cargar_contrato(servicio, alias)
        todos = contrato["components"]["schemas"]
        for nombre, esquema in todos.items():
            doc = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": f"https://nexum.com.mx/bienestar/contratos/{nombre}.schema.json",
                "title": nombre,
                "description": f"Generado desde el contrato OpenAPI de {servicio}. "
                               f"No editar a mano: ejecutar contratos/generar_json.py.",
                **reescribir_refs(esquema),
                "$defs": {k: reescribir_refs(v) for k, v in todos.items()
                          if k != nombre},
            }
            ruta = os.path.join(SALIDA, f"{nombre}.schema.json")
            with open(ruta, "w", encoding="utf8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)
                f.write("\n")
            escritos.append(os.path.basename(ruta))

    print(f"{len(escritos)} esquemas JSON generados en contratos/json/")
    for e in sorted(set(escritos)):
        print("  ", e)


if __name__ == "__main__":
    main()
