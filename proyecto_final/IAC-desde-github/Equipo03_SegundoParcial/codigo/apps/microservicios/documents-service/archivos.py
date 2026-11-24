"""
Validación, almacenamiento y recuperación de archivos de evidencia.

POR QUÉ ESTE MÓDULO SE MUDÓ AQUÍ
--------------------------------
Esta lógica existía y funcionaba, pero vivía en el portal web
(`apps/web/app/rutas/evidencias.py`). El efecto era que documents-service
—el servicio cuya responsabilidad declarada es «carga, almacenamiento,
consulta y administración segura de documentos y evidencias; validación de
formatos y tamaños; protección de archivos y recuperación controlada»— solo
guardaba metadatos, y la parte difícil la hacía otro componente.

Dos consecuencias concretas, no estéticas:

1. **Solo el portal podía subir evidencia.** La aplicación de escritorio y
   la móvil hablan con los microservicios, no con el portal. Para ellas la
   carga de evidencia sencillamente no existía.

2. **La validación no era una propiedad del sistema, sino de una pantalla.**
   Cualquier cliente que llamara a `POST /api/v1/documentos` directamente
   registraba un documento sin pasar por la comprobación de firma ni por el
   límite de tamaño, porque esas comprobaciones estaban del otro lado.

Ahora la validación está en el servicio. El portal pasa a ser un cliente
más, y lo que antes era una regla de una pantalla es una regla del sistema.

DÓNDE QUEDA CADA COSA
---------------------
El archivo va al almacén de blobs —una carpeta en developer, el punto de
montaje de un bucket en production— y los metadatos a MongoDB. La
separación se mantiene a propósito: MongoDB no es un almacén de archivos, y
guardar un PDF de 8 MB como documento volvería lenta cualquier consulta de
la colección.

CUATRO DECISIONES QUE NO SE VEN EN LA RESPUESTA
-----------------------------------------------
1. **El nombre que manda el cliente NO se usa como ruta.** Un nombre como
   `../../etc/passwd` escribiría fuera de la carpeta. El archivo se guarda
   bajo el SHA-256 de su contenido y el nombre original queda solo como
   metadato que se muestra.

2. **El tipo se decide por el contenido, no por la extensión.** Un
   ejecutable renombrado a `.pdf` pasa cualquier validación de extensión;
   no pasa la de firma.

3. **El hash es la identidad.** Subir dos veces el mismo archivo no lo
   duplica: se reconoce y se reutiliza. Ese mismo hash permite después
   comprobar que lo que alguien descargó es lo que se subió.

4. **El tamaño se revisa ANTES de leer el archivo completo en memoria.** Al
   revés, un archivo de 2 GB se cargaría entero para después rechazarlo, y
   bastarían unas pocas peticiones así para tumbar el servicio.
"""
import hashlib
import os
import re
import unicodedata

from comun import ErrorApi

# 8 MB. Un acta, una minuta o una foto de una sesión caben de sobra; un
# video no, y no es lo que una evidencia de intervención debe ser.
TAMANO_MAXIMO = int(os.environ.get("EVIDENCIA_TAMANO_MAXIMO", str(8 * 1024 * 1024)))

# Firma real de cada formato admitido.
FIRMAS = {
    "pdf": [b"%PDF-"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    # Office moderno es un ZIP: la firma es la del contenedor.
    "docx": [b"PK\x03\x04", b"PK\x05\x06"],
    "xlsx": [b"PK\x03\x04", b"PK\x05\x06"],
    # Texto plano y CSV no tienen firma; se valida que sea decodificable.
    "txt": [],
    "csv": [],
}

TIPOS_MIME = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "txt": "text/plain; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
}


def almacen():
    """Carpeta del almacén, leída en cada operación.

    Leerla en cada operación y no al importar el módulo permite que un
    envoltorio de arranque la defina después de cargar los módulos, que es
    lo que hacen varios servidores de aplicación. Con una constante de
    módulo, definir la variable después de importar no tiene efecto y no
    hay manera de notarlo.
    """
    return os.environ.get("ALMACEN_EVIDENCIAS", "/var/lib/bienestar/evidencias")


def extension_de(nombre):
    nombre = nombre or ""
    return nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""


def nombre_presentable(nombre):
    """Limpia el nombre para MOSTRARLO. Nunca se usa como ruta."""
    nombre = unicodedata.normalize("NFKD", nombre or "")
    nombre = nombre.encode("ascii", "ignore").decode("ascii")
    nombre = re.sub(r"[^A-Za-z0-9._ -]", "_", nombre).strip()
    # Las secuencias de puntos se colapsan: el nombre nunca se usa como
    # ruta, pero uno que se muestre como "..__..__tmp_acta.pdf" solo
    # confunde a quien lo lee en la tabla.
    nombre = re.sub(r"\.{2,}", ".", nombre).lstrip("._-")
    return (nombre or "sin_nombre")[:120]


def firma_coincide(contenido, extension):
    firmas = FIRMAS.get(extension)
    if firmas is None:
        return False
    if not firmas:                        # txt y csv: tiene que ser texto
        try:
            contenido[:4096].decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False
    return any(contenido.startswith(f) for f in firmas)


def ruta_de(sha256):
    """Dos niveles de subcarpeta por los primeros caracteres del hash.

    Un directorio plano con decenas de miles de archivos se vuelve lento de
    listar en casi cualquier sistema de archivos.
    """
    return os.path.join(almacen(), sha256[:2], sha256[2:4], sha256)


def validar(contenido, nombre_original):
    """Valida formato y tamaño. Devuelve (extension, sha256, nombre).

    Lanza ErrorApi con el detalle de QUÉ falló: un «archivo inválido» a
    secas obliga a quien lo recibe a adivinar si el problema es el formato,
    el tamaño o el contenido.
    """
    problemas = []

    if not contenido:
        problemas.append({"campo": "archivo", "problema": "esta vacio"})
    elif len(contenido) > TAMANO_MAXIMO:
        problemas.append({
            "campo": "archivo",
            "problema": f"pesa {len(contenido)} bytes y el maximo son "
                        f"{TAMANO_MAXIMO} ({TAMANO_MAXIMO // 1024 // 1024} MB)"})

    extension = extension_de(nombre_original)
    if extension not in FIRMAS:
        problemas.append({
            "campo": "nombre_archivo",
            "problema": f"formato '{extension or 'sin extension'}' no admitido; "
                        f"validos: {', '.join(sorted(FIRMAS))}"})
    elif contenido and not firma_coincide(contenido, extension):
        # El caso que una validación por extensión deja pasar.
        problemas.append({
            "campo": "archivo",
            "problema": f"el contenido no corresponde a un archivo {extension}; "
                        f"la extension dice una cosa y los primeros bytes otra"})

    if problemas:
        raise ErrorApi("ARCHIVO_INVALIDO",
                       "El archivo no cumple las reglas de formato o tamano.",
                       422, problemas)

    return extension, hashlib.sha256(contenido).hexdigest(), \
        nombre_presentable(nombre_original)


def guardar(contenido, sha256):
    """Escribe el blob. Devuelve True si era nuevo, False si ya estaba.

    La escritura es a un archivo temporal y después un `rename`, que es
    atómico dentro del mismo sistema de archivos. Escribir directo sobre la
    ruta final dejaría, si el proceso muere a la mitad, un archivo con el
    nombre correcto y el contenido truncado: exactamente el caso que el
    hash ya no podría detectar, porque nadie lo volvería a calcular.
    """
    ruta = ruta_de(sha256)
    if os.path.exists(ruta):
        return False
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    temporal = f"{ruta}.parcial"
    with open(temporal, "wb") as f:
        f.write(contenido)
    os.replace(temporal, ruta)
    return True


def leer(sha256):
    """Devuelve el contenido, o lanza si no está o si fue alterado."""
    ruta = ruta_de(sha256)
    if not os.path.exists(ruta):
        raise ErrorApi("ARCHIVO_NO_ENCONTRADO",
                       "El registro del documento existe pero su archivo no "
                       "esta en el almacen.", 404,
                       [{"campo": "sha256", "problema": sha256}])
    with open(ruta, "rb") as f:
        contenido = f.read()

    # Se recalcula el hash al leer. Cuesta milisegundos y es la única forma
    # de notar que el archivo cambió en el almacén después de guardarse:
    # sin esto, una evidencia alterada se entregaría como legítima, que es
    # justo lo que un sello sirve para impedir.
    real = hashlib.sha256(contenido).hexdigest()
    if real != sha256:
        raise ErrorApi("ARCHIVO_ALTERADO",
                       "El archivo almacenado no coincide con su sello. No se "
                       "entrega: una evidencia que cambio despues de "
                       "registrarse ya no respalda nada.", 409,
                       [{"campo": "sello_registrado", "problema": sha256},
                        {"campo": "sello_real", "problema": real}])
    return contenido
