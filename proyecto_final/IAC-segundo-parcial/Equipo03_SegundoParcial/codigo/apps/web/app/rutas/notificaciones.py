"""
Bandeja de notificaciones internas en el sistema web.

Es la pantalla que consume notifications-service. Hasta ahora el servicio
existía y nadie lo llamaba, lo que en la práctica significa que no estaba
probado contra un cliente real.

POR QUÉ AQUÍ NO HAY CAÍDA A POSTGRESQL
--------------------------------------
Las otras pantallas de administración caen a la base cuando su
microservicio no responde, porque los usuarios y los perfiles viven en
PostgreSQL y el microservicio solo es una vía de acceso. Las
notificaciones NO: viven únicamente en MongoDB, con un índice TTL que las
borra a los 90 días. No hay una segunda copia a la que caer, y fabricar
una lista vacía sería peor que decir la verdad: alguien podría creer que no
tiene avisos pendientes cuando lo que pasa es que el servicio está caído.

Así que cuando el servicio no responde, la pantalla lo dice y explica qué
se está perdiendo. Esa asimetría es deliberada y está documentada: una
degradación solo es válida cuando la información realmente existe en dos
lados.

LA RESTRICCIÓN DEL DOMINIO
--------------------------
Una notificación nunca contiene un valor de bienestar. El servicio rechaza
con 422 CIFRA_NO_PERMITIDA cualquier mensaje con una cifra decimal, porque
publicar «la carga percibida bajó a 2.9» por esta vía saltaría el mecanismo
de privacidad diferencial y el presupuesto de épsilon: el valor llegaría sin
ruido, sin umbral k y sin descontar nada del presupuesto.
"""
import os

import requests
from flask import (Blueprint, current_app, flash, g, redirect, render_template,
                   request, url_for)

from ..bitacora import registrar
from ..datos import consultar
from ..seguridad import COOKIE, requiere_permiso

bp = Blueprint("notificaciones", __name__, url_prefix="/notificaciones")

def _servicio():
    """Se lee en cada peticion, no al importar el modulo."""
    return os.environ.get("NOTIFICATIONS_SERVICE_URL", "")


def _tiempo_limite():
    return float(os.environ.get("MICROSERVICIO_TIMEOUT", "2.5"))


def _llamar(ruta, metodo="GET", json_cuerpo=None):
    """Devuelve (datos, None) o (None, motivo_legible).

    Nunca lanza: la pantalla tiene que poder explicar el problema.
    """
    servicio = _servicio()
    if not servicio:
        return None, ("Este ambiente no tiene configurada la direccion de "
                      "notifications-service (NOTIFICATIONS_SERVICE_URL).")
    try:
        token = request.cookies.get(COOKIE, "")
        r = requests.request(
            metodo, f"{servicio}{ruta}", json=json_cuerpo,
            headers={"Authorization": f"Bearer {token}",
                     "X-Correlacion-Id": getattr(g, "correlacion_id", "")},
            timeout=_tiempo_limite())
        if r.status_code >= 500:
            cuerpo = {}
            try:
                cuerpo = r.json()
            except Exception:
                pass
            motivo = (cuerpo.get("error") or {}).get("mensaje") or ""
            return None, (f"notifications-service respondio {r.status_code}. "
                          f"{motivo}")
        return r.json(), None
    except requests.Timeout:
        return None, (f"notifications-service no respondio en "
                      f"{_tiempo_limite()} s.")
    except Exception as e:
        current_app.logger.warning("notifications-service no respondio: %s", e)
        return None, ("No se pudo contactar a notifications-service. "
                      "Las notificaciones viven solo en MongoDB: no hay una "
                      "segunda copia en PostgreSQL a la que recurrir.")


@bp.get("/")
def bandeja():
    """Mis notificaciones. Cualquier perfil autenticado tiene bandeja."""
    if not g.get("sesion"):
        return redirect(url_for("sesion.entrar", siguiente=request.path))

    solo_sin_leer = request.args.get("sin_leer") == "1"
    try:
        pagina = max(1, int(request.args.get("pagina", 1)))
    except ValueError:
        pagina = 1

    consulta = f"?pagina={pagina}&tamano=20"
    if solo_sin_leer:
        consulta += "&solo_sin_leer=true"
    datos, problema = _llamar(f"/api/v1/notificaciones/mias{consulta}")

    notificaciones, paginacion, sin_leer = [], None, 0
    if datos:
        notificaciones = datos.get("notificaciones") or []
        paginacion = datos.get("paginacion")
        # El contador viene en la MISMA respuesta: pedirlo aparte seria una
        # segunda ida al servicio para un dato que ya se tiene, y las dos
        # podrian discrepar si alguien marca algo como leido entre ambas.
        sin_leer = datos.get("sin_leer", 0)

    return render_template("portal/notificaciones.html",
                           notificaciones=notificaciones,
                           paginacion=paginacion, sin_leer=sin_leer,
                           solo_sin_leer=solo_sin_leer, problema=problema)


@bp.post("/<notificacion_id>/leida")
def marcar_leida(notificacion_id):
    if not g.get("sesion"):
        return redirect(url_for("sesion.entrar"))
    datos, problema = _llamar(f"/api/v1/notificaciones/{notificacion_id}/leida",
                              "PUT")
    if problema:
        flash(problema, "error")
    else:
        # Quién leyó qué y cuándo queda en la bitácora: una notificación de
        # condición detectada es el aviso de que hay que actuar, y después
        # importa poder decir si el responsable la vio.
        registrar("NOTIFICACION_LEIDA", "EXITO", tipo_recurso="NOTIFICACION",
                  recurso=notificacion_id)
        flash("Notificacion marcada como leida.", "ok")
    return redirect(url_for("notificaciones.bandeja",
                            sin_leer=request.form.get("volver_sin_leer")))


@bp.get("/enviar")
@requiere_permiso("CAMPANIA_ADMIN", "INTERVENCION_APROBAR", "PARAMETRO_ADMIN")
def formulario_envio():
    unidades = consultar(
        "SELECT unidad_organizacional_id, nombre FROM "
        " organizacion.unidad_organizacional WHERE activa ORDER BY nombre")
    campanias = consultar(
        "SELECT campania_id, nombre FROM catalogo.campania "
        " ORDER BY secuencia DESC LIMIT 10")
    return render_template("portal/notificar.html", unidades=unidades,
                           campanias=campanias)


@bp.post("/enviar")
@requiere_permiso("CAMPANIA_ADMIN", "INTERVENCION_APROBAR", "PARAMETRO_ADMIN")
def enviar():
    cuerpo = {
        "tipo": request.form.get("tipo"),
        "titulo": (request.form.get("titulo") or "").strip(),
        "mensaje": (request.form.get("mensaje") or "").strip(),
    }
    unidad = request.form.get("unidad_organizacional_id") or ""
    campania = request.form.get("campania_id") or ""
    if unidad:
        cuerpo["unidad_organizacional_id"] = unidad
    if campania:
        cuerpo["campania_id"] = campania

    datos, problema = _llamar("/api/v1/notificaciones", "POST", cuerpo)
    if problema:
        flash(problema, "error")
        return redirect(url_for("notificaciones.formulario_envio"))

    error = (datos or {}).get("error")
    if error:
        if error.get("codigo") == "CIFRA_NO_PERMITIDA":
            flash("El servicio rechazo el mensaje porque contiene una cifra "
                  "decimal. Una notificacion no puede llevar un valor de "
                  "bienestar: llegaria sin ruido de Laplace, sin umbral k y "
                  "sin descontar nada del presupuesto de epsilon, es decir "
                  "saltandose todo el mecanismo de privacidad. Describe la "
                  "situacion en palabras y remite al panel para el detalle.",
                  "error")
        else:
            flash(f"{error.get('codigo')}: {error.get('mensaje')}", "error")
        return redirect(url_for("notificaciones.formulario_envio"))

    enviadas = (datos or {}).get("enviadas", 0)
    flash(f"{enviadas} notificacion(es) enviada(s).", "ok")
    return redirect(url_for("notificaciones.bandeja"))
