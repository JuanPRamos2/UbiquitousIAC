"""
Reportes y exportación en el sistema web.

Consume reports-service. Es la pantalla que cierra el requisito de reportes
y exportación del parcial, y la que vuelve usable el sello SHA-256: aquí se
genera el reporte, se descarga en CSV, JSON o XML, y se puede confrontar un
sello que llegó por otro medio contra el que quedó registrado.

POR QUÉ LA DESCARGA PASA POR EL PORTAL Y NO VA DIRECTA AL SERVICIO
------------------------------------------------------------------
El navegador podría pedirle el archivo a reports-service directamente. No
lo hace, por dos razones:

1. El token vive en una cookie HttpOnly del portal. Un enlace directo al
   microservicio tendría que llevar el token en la URL, donde queda en el
   historial del navegador, en los registros del proxy y en el encabezado
   Referer de la página siguiente.

2. El portal puede registrar la descarga en la bitácora de PostgreSQL con
   el actor de la sesión. La descarga es el momento en que la información
   sale del sistema, y es la que un comité querrá revisar.

El portal, por lo tanto, hace de intermediario: pide el archivo con el
token de la cookie y lo reenvía al navegador con las cabeceras de descarga.
"""
import os

import requests
from flask import (Blueprint, Response, current_app, flash, g, redirect,
                   render_template, request, url_for)

from ..bitacora import registrar
from ..datos import consultar
from ..seguridad import COOKIE, requiere_permiso

bp = Blueprint("reportes", __name__, url_prefix="/reportes")

def _servicio():
    """Se lee en cada peticion, no al importar el modulo."""
    return os.environ.get("REPORTS_SERVICE_URL", "")


def _tiempo_limite():
    return float(os.environ.get("MICROSERVICIO_TIMEOUT", "2.5"))
# Generar un reporte de cinco mil filas tarda más que una consulta normal,
# así que ese paso tiene su propio presupuesto de tiempo. Con el límite
# general de 2.5 s, un reporte legítimo se vería como un servicio caído.
TIEMPO_GENERAR = float(os.environ.get("REPORTE_TIMEOUT", "20"))

FORMATOS = ("json", "csv", "xml")


def _llamar(ruta, metodo="GET", json_cuerpo=None, tiempo=None, crudo=False):
    """Devuelve (respuesta, None) o (None, motivo_legible). Nunca lanza."""
    servicio = _servicio()
    if not servicio:
        return None, ("Este ambiente no tiene configurada la direccion de "
                      "reports-service (REPORTS_SERVICE_URL).")
    try:
        token = request.cookies.get(COOKIE, "")
        r = requests.request(
            metodo, f"{servicio}{ruta}", json=json_cuerpo,
            headers={"Authorization": f"Bearer {token}",
                     "X-Correlacion-Id": getattr(g, "correlacion_id", "")},
            timeout=tiempo or _tiempo_limite())
        if r.status_code >= 500:
            return None, f"reports-service respondio {r.status_code}."
        return (r if crudo else r.json()), None
    except requests.Timeout:
        return None, (f"reports-service no respondio en "
                      f"{tiempo or _tiempo_limite()} s.")
    except Exception as e:
        current_app.logger.warning("reports-service no respondio: %s", e)
        return None, ("No se pudo contactar a reports-service. Los reportes "
                      "generados viven en MongoDB a traves de ese servicio: "
                      "sin el no se pueden generar ni descargar, y el portal "
                      "no inventa una lista vacia.")


@bp.get("/")
@requiere_permiso("AGREGADO_UNIDAD", "AGREGADO_GLOBAL", "BITACORA_CONSULTAR",
                  "PARAMETRO_ADMIN", "RECOMENDACION_CONSULTAR",
                  "INTERVENCION_APROBAR", "INTERVENCION_SEGUIMIENTO")
def listar():
    try:
        pagina = max(1, int(request.args.get("pagina", 1)))
    except ValueError:
        pagina = 1
    tipo = (request.args.get("tipo") or "").strip().upper()

    consulta = f"?pagina={pagina}&tamano=15"
    if tipo:
        consulta += f"&tipo={tipo}"
    datos, problema = _llamar(f"/api/v1/reportes{consulta}")

    catalogo, problema_catalogo = _llamar("/api/v1/reportes/catalogo")
    tipos = (catalogo or {}).get("elementos", [])

    campanias = consultar(
        "SELECT campania_id, nombre FROM catalogo.campania "
        " ORDER BY secuencia DESC LIMIT 10")
    unidades = consultar(
        "SELECT unidad_organizacional_id, nombre "
        "  FROM organizacion.unidad_organizacional WHERE activa "
        " ORDER BY nombre")

    return render_template(
        "reportes/lista.html",
        reportes=(datos or {}).get("elementos", []),
        paginacion=(datos or {}).get("paginacion"),
        tipos=tipos, campanias=campanias, unidades=unidades,
        tipo_filtrado=tipo, formatos=FORMATOS,
        problema=problema or problema_catalogo)


@bp.post("/generar")
@requiere_permiso("AGREGADO_UNIDAD", "AGREGADO_GLOBAL", "BITACORA_CONSULTAR",
                  "PARAMETRO_ADMIN", "RECOMENDACION_CONSULTAR",
                  "INTERVENCION_APROBAR", "INTERVENCION_SEGUIMIENTO")
def generar():
    tipo = (request.form.get("tipo") or "").strip().upper()
    parametro = (request.form.get("parametro") or "").strip() or None
    if not tipo:
        flash("Elige el tipo de reporte.", "error")
        return redirect(url_for("reportes.listar"))

    cuerpo = {"tipo": tipo}
    if parametro:
        cuerpo["parametro"] = parametro
    datos, problema = _llamar("/api/v1/reportes", "POST", cuerpo,
                              tiempo=TIEMPO_GENERAR)
    if problema:
        flash(problema, "error")
        return redirect(url_for("reportes.listar"))

    error = (datos or {}).get("error")
    if error:
        codigo = error.get("codigo")
        if codigo == "SIN_DATOS":
            flash("La consulta no devolvio filas. Revisa el parametro: el "
                  "servicio no entrega un reporte vacio a proposito, porque "
                  "un archivo sin filas se confunde con una campania sin "
                  "supresiones.", "aviso")
        elif codigo == "VALIDACION":
            detalle = (error.get("detalles") or [{}])[0]
            flash(f"Ese reporte exige el parametro "
                  f"'{detalle.get('problema', '')}'.", "error")
        else:
            flash(f"{codigo}: {error.get('mensaje')}", "error")
        return redirect(url_for("reportes.listar"))

    flash(f"Reporte {datos['reporte_id']} generado: {datos['total_filas']} "
          f"filas, {datos['filas_suprimidas']} sin valor por supresion. "
          f"Sello {datos['sello_sha256'][:16]}…", "ok")
    return redirect(url_for("reportes.listar"))


@bp.get("/<reporte_id>/descargar")
@requiere_permiso("AGREGADO_UNIDAD", "AGREGADO_GLOBAL", "BITACORA_CONSULTAR",
                  "PARAMETRO_ADMIN", "RECOMENDACION_CONSULTAR",
                  "INTERVENCION_APROBAR", "INTERVENCION_SEGUIMIENTO")
def descargar(reporte_id):
    """Reenvía el archivo al navegador. El token no sale de la cookie."""
    formato = (request.args.get("formato") or "csv").strip().lower()
    if formato not in FORMATOS:
        flash(f"Formato no soportado. Validos: {', '.join(FORMATOS)}.", "error")
        return redirect(url_for("reportes.listar"))

    respuesta, problema = _llamar(
        f"/api/v1/reportes/{reporte_id}/contenido?formato={formato}",
        tiempo=TIEMPO_GENERAR, crudo=True)
    if problema:
        flash(problema, "error")
        return redirect(url_for("reportes.listar"))
    if respuesta.status_code != 200:
        flash(f"El servicio respondio {respuesta.status_code} al descargar.",
              "error")
        return redirect(url_for("reportes.listar"))

    registrar("REPORTE_DESCARGADO", "EXITO", tipo_recurso="REPORTE",
              recurso=f"{reporte_id}:{formato}")
    return Response(
        respuesta.content, 200,
        {"Content-Type": respuesta.headers.get("Content-Type",
                                               "application/octet-stream"),
         "Content-Disposition": respuesta.headers.get(
             "Content-Disposition", f'attachment; filename="{reporte_id}.{formato}"'),
         # El sello viaja también al navegador: quien recibe el archivo
         # puede confrontarlo después sin volver a pedir nada.
         "X-Reporte-Sello": respuesta.headers.get("X-Reporte-Sello", ""),
         "X-Content-Type-Options": "nosniff"})


@bp.post("/<reporte_id>/verificar")
@requiere_permiso("BITACORA_CONSULTAR", "PARAMETRO_ADMIN")
def verificar(reporte_id):
    """Confronta un sello que llegó por otro medio contra el registrado."""
    sello = (request.form.get("sello_sha256") or "").strip()
    if len(sello) != 64:
        flash("Un sello SHA-256 tiene 64 caracteres hexadecimales.", "error")
        return redirect(url_for("reportes.listar"))

    datos, problema = _llamar(f"/api/v1/reportes/{reporte_id}/verificar", "POST",
                              {"sello_sha256": sello})
    if problema:
        flash(problema, "error")
        return redirect(url_for("reportes.listar"))
    error = (datos or {}).get("error")
    if error:
        flash(f"{error.get('codigo')}: {error.get('mensaje')}", "error")
        return redirect(url_for("reportes.listar"))

    registrar("REPORTE_VERIFICADO",
              "EXITO" if datos.get("coincide") else "RECHAZADO",
              tipo_recurso="REPORTE", recurso=reporte_id)
    if datos.get("coincide"):
        flash(f"El sello coincide: el archivo es el que genero el sistema. "
              f"{datos.get('mensaje', '')}", "ok")
    else:
        flash(f"El sello NO coincide. {datos.get('mensaje', '')} "
              f"El registrado es {datos.get('sello_registrado', '')[:16]}…",
              "error")
    return redirect(url_for("reportes.listar"))
