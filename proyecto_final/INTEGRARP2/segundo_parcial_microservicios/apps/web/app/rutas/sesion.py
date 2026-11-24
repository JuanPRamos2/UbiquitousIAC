"""Inicio y cierre de sesión."""
from flask import (Blueprint, current_app, flash, g, redirect, render_template,
                   request, url_for)

from ..bitacora import registrar
from ..config import Config
from ..datos import ejecutar
from ..seguridad import (COOKIE, contar_intento_fallido, emitir_token,
                         esta_bloqueado, limpiar_intentos, revocar,
                         verificar_credenciales)

bp = Blueprint("sesion", __name__)


@bp.route("/entrar", methods=["GET", "POST"])
def entrar():
    siguiente = request.args.get("siguiente") or url_for("portal.inicio")
    if g.get("sesion"):
        return redirect(siguiente)

    if request.method == "GET":
        return render_template("publico/entrar.html", siguiente=siguiente)

    correo = (request.form.get("correo") or "").strip()
    contrasena = request.form.get("contrasena") or ""

    if esta_bloqueado(correo):
        registrar("LOGIN_FALLIDO", "RECHAZADO", tipo_recurso="USUARIO",
                  recurso=correo, perfil="ANONIMO")
        flash("Demasiados intentos fallidos. Espera unos minutos antes de "
              "volver a intentarlo.", "error")
        return render_template("publico/entrar.html", siguiente=siguiente), 429

    usuario = verificar_credenciales(correo, contrasena)
    if not usuario:
        n = contar_intento_fallido(correo)
        registrar("LOGIN_FALLIDO", "RECHAZADO", tipo_recurso="USUARIO",
                  recurso=correo, perfil="ANONIMO")
        # El mensaje no distingue entre correo inexistente y contraseña
        # incorrecta: decirlo permitiría averiguar qué correos existen.
        restantes = max(0, Config.INTENTOS_MAXIMOS - n)
        flash(f"Correo o contraseña incorrectos. Intentos restantes: {restantes}.", "error")
        return render_template("publico/entrar.html", siguiente=siguiente), 401

    limpiar_intentos(correo)
    token, jti = emitir_token(usuario["usuario_id"], usuario["perfil_id"],
                              usuario["perfil"], usuario["unidad_alcance_id"])
    registrar("LOGIN_EXITOSO", "EXITO", tipo_recurso="USUARIO",
              recurso=usuario["usuario_id"], actor=usuario["usuario_id"],
              perfil=usuario["perfil"])
    try:
        ejecutar("UPDATE usuarios.usuario SET fecha_ultimo_acceso = now() "
                 "WHERE usuario_id = %s", (usuario["usuario_id"],))
    except Exception:
        current_app.logger.warning("No se pudo actualizar fecha_ultimo_acceso")

    resp = redirect(siguiente)
    resp.set_cookie(
        COOKIE, token,
        httponly=True,                       # el JavaScript de la página no lo lee
        samesite="Lax",                      # no viaja en peticiones de otros sitios
        secure=(Config.AMBIENTE != "developer"),  # solo por HTTPS fuera de developer
        max_age=Config.JWT_MINUTOS * 60,
    )
    return resp


@bp.post("/salir")
def salir():
    sesion = g.get("sesion")
    if sesion:
        # Revocar de inmediato: sin esto el token seguiría siendo válido
        # hasta su expiración aunque la persona haya cerrado sesión.
        revocar(sesion.get("jti", ""))
        registrar("LOGOUT", "EXITO", tipo_recurso="USUARIO",
                  recurso=sesion.get("sub"), actor=sesion.get("sub"),
                  perfil=sesion.get("perfil"))
    resp = redirect(url_for("publico.inicio"))
    resp.delete_cookie(COOKIE)
    return resp
