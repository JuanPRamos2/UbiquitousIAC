"""
Carga de archivos de evidencia.

QUÉ ES UNA EVIDENCIA AQUÍ
-------------------------
El acta de una sesión de acompañamiento, la minuta de un comité, el
material de una campaña de descanso: documentos que respaldan que un plan
de intervención se ejecutó de verdad. Sin ellos, el seguimiento de una
intervención es la palabra de quien la reporta.

DÓNDE QUEDA CADA COSA, Y QUIÉN DECIDE QUÉ
-----------------------------------------
Esta pantalla ya NO valida ni almacena nada por su cuenta: recibe el
archivo del navegador y se lo entrega a documents-service, que es el
servicio cuya responsabilidad declarada incluye la validación de formatos
y tamaños y la protección de los archivos.

Antes la validación vivía aquí, y el efecto era doble: la aplicación de
escritorio y la móvil no podían adjuntar evidencia —hablan con los
microservicios, no con el portal—, y cualquier cliente que llamara al
servicio directamente registraba un documento sin pasar por ninguna
comprobación, porque la comprobación estaba de este lado.

Mantener una copia de las reglas aquí sería peor que no tenerlas: habría
dos verdades sobre qué archivo es válido y nada que obligue a que
coincidan. Por eso este módulo quedó corto a propósito.

El archivo sigue yendo al almacén de blobs y los metadatos a MongoDB; lo
que cambió es QUIÉN lo hace.

SEIS DECISIONES QUE NO SE VEN EN LA PANTALLA
--------------------------------------------
1. **El nombre del archivo que manda el navegador NO se usa como ruta.**
   Un nombre como `../../etc/passwd` escribiría fuera de la carpeta. El
   archivo se guarda bajo el SHA-256 de su contenido, y el nombre original
   se conserva solo como metadato.

2. **El tipo se decide por el contenido, no por la extensión.** Un
   ejecutable renombrado a `.pdf` pasaría cualquier validación de
   extensión. Se leen los primeros bytes y se compara con la firma del
   formato declarado.

3. **El hash es la identidad.** Subir dos veces el mismo archivo no lo
   duplica: se reconoce y se reutiliza. Y ese mismo hash permite después
   verificar que el archivo que alguien descargó es el que se subió.

4. **Una evidencia no se modifica.** Una corrección es un archivo nuevo
   con su propia fecha; el anterior se conserva. Es la misma regla que
   documents-service aplica a las evidencias de consentimiento, y por el
   mismo motivo: una evidencia editable no es evidencia.

5. **No se aceptan archivos sin intervención ni unidad.** Un archivo
   suelto, sin saber a qué plan pertenece, es basura que nadie podrá
   interpretar en seis meses.

6. **Se registra la descarga, no solo la carga.** La carga es trabajo
   normal; la descarga es el momento en que la información sale del
   sistema, y es la que un comité querrá revisar.
"""
import base64
import os

import requests
from flask import (Blueprint, Response, current_app, flash, g, redirect,
                   render_template, request, url_for)

from ..bitacora import registrar
from ..datos import consultar, consultar_uno
from ..seguridad import COOKIE, requiere_permiso

bp = Blueprint("evidencias", __name__, url_prefix="/evidencias")

def _servicio():
    """Se lee en cada peticion, no al importar el modulo."""
    return os.environ.get("DOCUMENTS_SERVICE_URL", "")


def _tiempo_limite():
    return float(os.environ.get("MICROSERVICIO_TIMEOUT", "2.5"))

# Los formatos y el límite los decide documents-service. Aquí solo se
# guardan para poder DIBUJAR la pantalla —decirle a quien sube qué se
# admite— y se piden al servicio al cargar la vista. Si el servicio no
# responde se usan estos valores, que son los mismos que trae por omisión:
# una lista de formatos desactualizada estorba, pero no deja pasar nada,
# porque quien valida es el servicio.
FORMATOS_PARA_MOSTRAR = ("csv", "docx", "jpg", "pdf", "png", "txt", "xlsx")
TAMANO_MAXIMO_PARA_MOSTRAR = int(
    os.environ.get("EVIDENCIA_TAMANO_MAXIMO", str(8 * 1024 * 1024)))


def _llamar_documentos(ruta, metodo="GET", json_cuerpo=None, tiempo=None):
    servicio = _servicio()
    if not servicio:
        return None, ("Este ambiente no tiene configurada la direccion de "
                      "documents-service (DOCUMENTS_SERVICE_URL).")
    try:
        token = request.cookies.get(COOKIE, "")
        r = requests.request(
            metodo, f"{servicio}{ruta}", json=json_cuerpo,
            headers={"Authorization": f"Bearer {token}",
                     "X-Correlacion-Id": getattr(g, "correlacion_id", "")},
            timeout=tiempo or _tiempo_limite())
        if r.status_code >= 500:
            return None, f"documents-service respondio {r.status_code}."
        return r.json(), None
    except Exception as e:
        current_app.logger.warning("documents-service no respondio: %s", e)
        return None, ("No se pudo contactar a documents-service. Los "
                      "metadatos de las evidencias viven en MongoDB a traves "
                      "de ese servicio: sin el, el archivo se podria guardar "
                      "pero quedaria sin registro, que es peor que no "
                      "guardarlo.")


@bp.get("/")
@requiere_permiso("INTERVENCION_SEGUIMIENTO", "INTERVENCION_APROBAR",
                  "BITACORA_CONSULTAR")
def listar():
    intervencion = request.args.get("intervencion_id") or ""
    consulta = "?tipo=REPORTE_ORGANIZACIONAL&tamano=50"
    datos, problema = _llamar_documentos(f"/api/v1/documentos{consulta}")

    evidencias = []
    for d in (datos or {}).get("elementos", []):
        contenido = d.get("contenido") or {}
        if contenido.get("clase") != "EVIDENCIA_ARCHIVO":
            continue
        if intervencion and contenido.get("intervencion_id") != intervencion:
            continue
        evidencias.append({**d, **contenido})

    planes = consultar(
        "SELECT p.intervencion_id, p.tipo_intervencion, p.estado, "
        "       uo.nombre AS unidad, p.unidad_organizacional_id "
        "  FROM intervencion.plan p "
        "  JOIN organizacion.unidad_organizacional uo "
        "       USING (unidad_organizacional_id) "
        " ORDER BY p.fecha_inicio DESC LIMIT 50")

    return render_template("intervencion/evidencias.html", evidencias=evidencias,
                           planes=planes, problema=problema,
                           intervencion=intervencion,
                           formatos=sorted(FORMATOS_PARA_MOSTRAR),
                           tamano_maximo_mb=round(TAMANO_MAXIMO_PARA_MOSTRAR / 1024 / 1024, 1))


@bp.post("/")
@requiere_permiso("INTERVENCION_SEGUIMIENTO", "INTERVENCION_APROBAR")
def subir():
    """Entrega el archivo a documents-service. Aquí no se valida nada.

    Las únicas comprobaciones que quedan son las de la FORMA del
    formulario —que venga un archivo, un plan y una descripción—, porque
    son las que permiten contestar sin gastar una ida y vuelta. Si el
    archivo es válido o no lo decide el servicio, que es quien va a
    guardarlo.
    """
    archivo = request.files.get("archivo")
    intervencion_id = (request.form.get("intervencion_id") or "").strip()
    descripcion = (request.form.get("descripcion") or "").strip()

    if not archivo or not archivo.filename:
        flash("Elige un archivo.", "error")
        return redirect(url_for("evidencias.listar"))
    if not intervencion_id:
        flash("Indica a que plan de intervencion pertenece. Un archivo suelto, "
              "sin saber a que plan corresponde, es basura que nadie podra "
              "interpretar en seis meses.", "error")
        return redirect(url_for("evidencias.listar"))
    if len(descripcion) < 10:
        flash("Describe que es el archivo (al menos 10 caracteres).", "error")
        return redirect(url_for("evidencias.listar"))

    # Se lee un byte más que el límite para poder distinguir «justo en el
    # límite» de «se pasa», sin cargar en memoria un archivo enorme.
    contenido = archivo.read(TAMANO_MAXIMO_PARA_MOSTRAR + 1)

    cuerpo = {
        "intervencion_id": intervencion_id,
        "nombre_archivo": archivo.filename,
        "descripcion": descripcion,
        "contenido_base64": base64.b64encode(contenido).decode("ascii"),
    }
    datos, problema = _llamar_documentos(
        "/api/v1/documentos/archivos", "POST", cuerpo,
        tiempo=float(os.environ.get("EVIDENCIA_TIMEOUT", "20")))
    if problema:
        flash(problema, "error")
        return redirect(url_for("evidencias.listar"))

    error = (datos or {}).get("error")
    if error:
        # El servicio explica QUÉ falló —formato, tamaño, firma— en los
        # detalles. Mostrarlos es lo que permite corregir; un «no se pudo»
        # obliga a adivinar.
        detalle = " ".join(d.get("problema", "")
                           for d in (error.get("detalles") or []))
        registrar("EVIDENCIA_CARGADA", "RECHAZADO",
                  tipo_recurso="EVIDENCIA", recurso=intervencion_id)
        flash(f"{error.get('mensaje')} {detalle}".strip(), "error")
        return redirect(url_for("evidencias.listar"))

    sello = (datos or {}).get("sha256", "")
    registrar("EVIDENCIA_CARGADA", "EXITO", tipo_recurso="EVIDENCIA",
              recurso=f"{intervencion_id}:{sello[:16]}")
    if datos.get("archivo_nuevo") is False:
        flash("Archivo registrado. El contenido ya estaba almacenado (mismo "
              "SHA-256): no se duplico, se reutilizo.", "ok")
    else:
        flash(f"Evidencia cargada ({(datos.get('bytes') or 0) // 1024} KB). "
              f"Sello SHA-256: {sello[:16]}…", "ok")
    return redirect(url_for("evidencias.listar", intervencion_id=intervencion_id))


@bp.get("/<documento_id>/archivo")
@requiere_permiso("INTERVENCION_SEGUIMIENTO", "INTERVENCION_APROBAR",
                  "BITACORA_CONSULTAR")
def descargar(documento_id):
    """Pide el archivo a documents-service y lo reenvía al navegador.

    El portal hace de intermediario en lugar de enlazar directo al
    servicio, por la misma razón que en la pantalla de reportes: el token
    vive en una cookie HttpOnly, y un enlace directo tendría que llevarlo
    en la URL, donde queda en el historial del navegador, en los registros
    del proxy y en el encabezado Referer de la página siguiente.

    El sello sale del documento REGISTRADO, nunca de la URL: así nadie
    puede pedir un archivo arbitrario del almacén pasando un hash.
    """
    datos, problema = _llamar_documentos(f"/api/v1/documentos/{documento_id}")
    if problema:
        flash(problema, "error")
        return redirect(url_for("evidencias.listar"))
    documento = (datos or {}).get("documento") or datos or {}
    contenido = documento.get("contenido") or {}
    sello = contenido.get("sha256") or ""
    if not sello:
        flash("Ese documento no es una evidencia con archivo.", "error")
        return redirect(url_for("evidencias.listar"))

    servicio = _servicio()
    if not servicio:
        flash("Este ambiente no tiene configurada la direccion de "
              "documents-service (DOCUMENTS_SERVICE_URL).", "error")
        return redirect(url_for("evidencias.listar"))

    try:
        r = requests.get(
            f"{servicio}/api/v1/documentos/archivos/{sello}",
            headers={"Authorization": f"Bearer {request.cookies.get(COOKIE, '')}",
                     "X-Correlacion-Id": getattr(g, "correlacion_id", "")},
            timeout=float(os.environ.get("EVIDENCIA_TIMEOUT", "20")))
    except Exception as e:
        current_app.logger.warning("documents-service no respondio: %s", e)
        flash("No se pudo contactar a documents-service para traer el "
              "archivo.", "error")
        return redirect(url_for("evidencias.listar"))

    if r.status_code != 200:
        # El servicio distingue «no esta» de «fue alterado», y esa
        # diferencia es justamente la que el sello sirve para detectar.
        try:
            error = r.json().get("error", {})
            mensaje = f"{error.get('codigo')}: {error.get('mensaje')}"
        except Exception:
            mensaje = f"documents-service respondio {r.status_code}."
        registrar("EVIDENCIA_DESCARGADA", "RECHAZADO",
                  tipo_recurso="EVIDENCIA", recurso=documento_id)
        flash(mensaje, "error")
        return redirect(url_for("evidencias.listar"))

    registrar("EVIDENCIA_DESCARGADA", "EXITO", tipo_recurso="EVIDENCIA",
              recurso=documento_id)
    return Response(
        r.content, 200,
        {"Content-Type": r.headers.get("Content-Type",
                                       "application/octet-stream"),
         "Content-Disposition": r.headers.get(
             "Content-Disposition", f'attachment; filename="{documento_id}"'),
         "X-Evidencia-Sello": sello,
         # Sin esto, un navegador podria interpretar el archivo en lugar de
         # descargarlo.
         "X-Content-Type-Options": "nosniff"})
