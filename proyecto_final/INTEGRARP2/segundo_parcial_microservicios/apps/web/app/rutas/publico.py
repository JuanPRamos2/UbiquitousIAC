"""Sitio público: lo que puede ver cualquiera sin iniciar sesión."""
from flask import Blueprint, render_template

from ..bitacora import registrar
from ..datos import consultar, consultar_uno

bp = Blueprint("publico", __name__)


@bp.get("/")
def inicio():
    return render_template("publico/inicio.html")


@bp.get("/transparencia")
def transparencia():
    """Qué hace el sistema con los datos, en lenguaje llano.

    Esta página es pública a propósito: una promesa de privacidad que solo
    se puede leer después de iniciar sesión no sirve para decidir si
    participar.
    """
    secciones = consultar(
        "SELECT titulo, contenido, orden FROM transparencia.seccion "
        "WHERE publicada ORDER BY orden")
    return render_template("publico/transparencia.html", secciones=secciones)


@bp.get("/aviso-de-privacidad")
def aviso():
    av = consultar_uno(
        """SELECT aviso_id, version, fecha_vigencia, datos_capturados, finalidad,
                  plazo_retencion, quien_accede, quien_no_accede, forma_agregacion,
                  explicacion_k, explicacion_dp, consecuencias_revocar,
                  politica_retencion, canal_contacto
             FROM consentimiento.aviso_privacidad
            WHERE vigente ORDER BY version DESC LIMIT 1""")
    registrar("AVISO_CONSULTADO", "EXITO", tipo_recurso="AVISO",
              recurso=av["aviso_id"] if av else None)
    return render_template("publico/aviso.html", aviso=av)
