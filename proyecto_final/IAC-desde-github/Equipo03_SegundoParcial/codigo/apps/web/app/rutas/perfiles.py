"""
Administración de perfiles y de su matriz de permisos.

POR QUÉ ESTA PANTALLA EXISTE
----------------------------
El RBAC del proyecto es dirigido por datos: un permiso es una fila de
`usuarios.permiso` y la asignación es una fila de `usuarios.perfil_permiso`.
Eso se afirma en el documento de actores desde el primer parcial, pero
mientras los cinco perfiles solo se pudieran crear con un INSERT a mano, la
afirmación no era comprobable. Aquí se vuelve comprobable: se crea un
perfil nuevo desde el navegador, se le asignan permisos, y las rutas de los
ocho microservicios lo aceptan sin recompilar ni volver a desplegar nada,
porque todos consultan la misma tabla en cada petición.

TRES RESGUARDOS QUE NO SON ADORNO
---------------------------------
1. **Nadie se quita a sí mismo USUARIO_ADMIN.** Sin esto, un administrador
   distraído deja el sistema sin nadie que pueda administrar usuarios, y la
   única salida es entrar a la base de datos a mano.

2. **Siempre queda al menos un perfil con USUARIO_ADMIN asignado a un
   usuario activo.** Es el mismo riesgo por otra vía: quitarle el permiso
   al único perfil que lo tiene deja el sistema igual de bloqueado.

3. **Un permiso sensible exige justificación escrita.** Los permisos con
   `sensible = true` dan acceso a agregados de bienestar, a la bitácora o a
   los parámetros de privacidad. Conceder uno queda en la bitácora con el
   motivo que escribió quien lo concedió; sin motivo, no se concede. Un
   comité de privacidad puede entonces preguntar por qué tal perfil ve
   tendencias, y la respuesta está escrita.

Lo que esta pantalla NO hace: borrar perfiles. Un perfil con usuarios
asignados no se puede borrar sin romper llaves foráneas, y uno sin usuarios
igual aparece en la bitácora histórica. Se desactiva.
"""
from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from ..bitacora import registrar
from ..datos import consultar, consultar_uno, cursor
from ..seguridad import requiere_permiso

bp = Blueprint("perfiles", __name__, url_prefix="/administracion/perfiles")

# Un código de perfil es una constante que viaja en los tokens y en la
# bitácora: se acota su forma para que nadie cree 'Líder de Área (nuevo)'.
import re
FORMA_CODIGO = re.compile(r"^[A-Z][A-Z0-9_]{2,29}$")


def _perfiles_con_cuentas():
    return consultar(
        "SELECT p.perfil_id, p.codigo, p.nombre, p.descripcion, p.activo, "
        "       count(DISTINCT up.usuario_id) AS usuarios, "
        "       count(DISTINCT pp.permiso_id) AS permisos, "
        "       count(DISTINCT CASE WHEN pm.sensible THEN pm.permiso_id END) "
        "         AS permisos_sensibles "
        "  FROM usuarios.perfil p "
        "  LEFT JOIN usuarios.usuario_perfil up ON up.perfil_id = p.perfil_id "
        "  LEFT JOIN usuarios.perfil_permiso pp ON pp.perfil_id = p.perfil_id "
        "  LEFT JOIN usuarios.permiso pm ON pm.permiso_id = pp.permiso_id "
        " GROUP BY p.perfil_id, p.codigo, p.nombre, p.descripcion, p.activo "
        " ORDER BY p.perfil_id")


def _quedaria_sin_administradores(perfil_id, permiso_codigo):
    """¿Quitar este permiso a este perfil deja al sistema sin administración?

    Se comprueba contra usuarios ACTIVOS: un perfil con el permiso pero sin
    nadie que lo use no salva a nadie.
    """
    if permiso_codigo != "USUARIO_ADMIN":
        return False
    fila = consultar_uno(
        "SELECT count(*) AS n "
        "  FROM usuarios.perfil_permiso pp "
        "  JOIN usuarios.permiso pm ON pm.permiso_id = pp.permiso_id "
        "  JOIN usuarios.usuario_perfil up ON up.perfil_id = pp.perfil_id "
        "  JOIN usuarios.usuario u ON u.usuario_id = up.usuario_id "
        " WHERE pm.codigo = 'USUARIO_ADMIN' AND u.activo "
        "   AND pp.perfil_id <> %s", (perfil_id,))
    return (fila or {}).get("n", 0) == 0


@bp.get("/")
@requiere_permiso("USUARIO_ADMIN")
def listar():
    return render_template("admin/perfiles.html",
                           perfiles=_perfiles_con_cuentas())


@bp.post("/")
@requiere_permiso("USUARIO_ADMIN")
def crear():
    """Un perfil nuevo es una fila, no un despliegue."""
    codigo = (request.form.get("codigo") or "").strip().upper()
    nombre = (request.form.get("nombre") or "").strip()
    descripcion = (request.form.get("descripcion") or "").strip() or None

    if not FORMA_CODIGO.match(codigo):
        flash("El codigo debe ir en MAYUSCULAS, empezar con letra y usar solo "
              "letras, numeros y guion bajo (3 a 30 caracteres). Viaja en los "
              "tokens y en la bitacora, por eso se acota su forma.", "error")
        return redirect(url_for("perfiles.listar"))
    if len(nombre) < 4:
        flash("Escribe un nombre legible para el perfil.", "error")
        return redirect(url_for("perfiles.listar"))

    if consultar_uno("SELECT 1 FROM usuarios.perfil WHERE codigo = %s", (codigo,)):
        flash(f"Ya existe un perfil con el codigo {codigo}.", "error")
        return redirect(url_for("perfiles.listar"))

    with cursor(commit=True) as cur:
        cur.execute("INSERT INTO usuarios.perfil (codigo, nombre, descripcion, activo) "
                    "VALUES (%s, %s, %s, TRUE) RETURNING perfil_id",
                    (codigo, nombre, descripcion))
        nuevo = cur.fetchone()["perfil_id"]

    registrar("PERFIL_MODIFICADO", "EXITO", tipo_recurso="PERFIL", recurso=codigo)
    flash(f"Perfil {codigo} creado (#{nuevo}). Nace SIN permisos: asignalos "
          f"abajo, uno por uno y a proposito.", "ok")
    return redirect(url_for("perfiles.matriz", perfil_id=nuevo))


@bp.post("/<int:perfil_id>/estado")
@requiere_permiso("USUARIO_ADMIN")
def cambiar_estado(perfil_id):
    activo = request.form.get("activo") == "1"
    perfil = consultar_uno("SELECT codigo FROM usuarios.perfil WHERE perfil_id = %s",
                           (perfil_id,))
    if not perfil:
        flash("Ese perfil no existe.", "error")
        return redirect(url_for("perfiles.listar"))

    if not activo:
        if perfil_id == g.sesion.get("perfil_id"):
            flash("No puedes desactivar tu propio perfil.", "error")
            return redirect(url_for("perfiles.listar"))
        if _quedaria_sin_administradores(perfil_id, "USUARIO_ADMIN"):
            flash("Ese es el unico perfil con USUARIO_ADMIN en manos de una "
                  "cuenta activa: desactivarlo dejaria al sistema sin nadie "
                  "que pueda administrar usuarios.", "error")
            return redirect(url_for("perfiles.listar"))
        con_usuarios = consultar_uno(
            "SELECT count(*) AS n FROM usuarios.usuario_perfil WHERE perfil_id = %s",
            (perfil_id,))
        if (con_usuarios or {}).get("n", 0):
            flash(f"El perfil {perfil['codigo']} queda inactivo, pero "
                  f"{con_usuarios['n']} cuenta(s) lo siguen teniendo asignado: "
                  f"reasignalas para que dejen de autorizar con el.", "aviso")

    with cursor(commit=True) as cur:
        cur.execute("UPDATE usuarios.perfil SET activo = %s WHERE perfil_id = %s",
                    (activo, perfil_id))
    registrar("PERFIL_MODIFICADO", "EXITO", tipo_recurso="PERFIL",
              recurso=perfil["codigo"])
    flash(f"Perfil {perfil['codigo']} {'activado' if activo else 'desactivado'}.",
          "ok")
    return redirect(url_for("perfiles.listar"))


@bp.get("/<int:perfil_id>")
@requiere_permiso("USUARIO_ADMIN")
def matriz(perfil_id):
    perfil = consultar_uno(
        "SELECT perfil_id, codigo, nombre, descripcion, activo "
        "  FROM usuarios.perfil WHERE perfil_id = %s", (perfil_id,))
    if not perfil:
        flash("Ese perfil no existe.", "error")
        return redirect(url_for("perfiles.listar"))

    permisos = consultar(
        "SELECT pm.permiso_id, pm.codigo, pm.descripcion, pm.sensible, "
        "       (pp.perfil_id IS NOT NULL) AS asignado "
        "  FROM usuarios.permiso pm "
        "  LEFT JOIN usuarios.perfil_permiso pp "
        "         ON pp.permiso_id = pm.permiso_id AND pp.perfil_id = %s "
        " ORDER BY pm.sensible, pm.codigo", (perfil_id,))
    cuentas = consultar(
        "SELECT u.usuario_id, u.nombre, u.apellido_paterno, u.correo, u.activo "
        "  FROM usuarios.usuario_perfil up "
        "  JOIN usuarios.usuario u USING (usuario_id) "
        " WHERE up.perfil_id = %s ORDER BY u.usuario_id LIMIT 50", (perfil_id,))
    return render_template("admin/perfil_permisos.html", perfil=perfil,
                           permisos=permisos, cuentas=cuentas,
                           es_mi_perfil=(perfil_id == g.sesion.get("perfil_id")))


@bp.post("/<int:perfil_id>/permisos")
@requiere_permiso("USUARIO_ADMIN")
def cambiar_permiso(perfil_id):
    """Concede o retira UN permiso. Deja constancia con el motivo."""
    try:
        permiso_id = int(request.form.get("permiso_id") or 0)
    except ValueError:
        permiso_id = 0
    conceder = request.form.get("conceder") == "1"
    motivo = (request.form.get("motivo") or "").strip()

    permiso = consultar_uno(
        "SELECT permiso_id, codigo, sensible FROM usuarios.permiso "
        " WHERE permiso_id = %s", (permiso_id,))
    perfil = consultar_uno("SELECT codigo FROM usuarios.perfil WHERE perfil_id = %s",
                           (perfil_id,))
    if not permiso or not perfil:
        flash("Perfil o permiso invalido.", "error")
        return redirect(url_for("perfiles.listar"))

    # ---- resguardos ----
    if not conceder and permiso["codigo"] == "USUARIO_ADMIN":
        if perfil_id == g.sesion.get("perfil_id"):
            flash("No puedes quitarle USUARIO_ADMIN a tu propio perfil: "
                  "te quedarias fuera de esta pantalla y la unica salida "
                  "seria entrar a la base de datos a mano.", "error")
            return redirect(url_for("perfiles.matriz", perfil_id=perfil_id))
        if _quedaria_sin_administradores(perfil_id, "USUARIO_ADMIN"):
            flash("Es el unico perfil con USUARIO_ADMIN en manos de una cuenta "
                  "activa. Asigna el permiso a otro perfil antes de quitarlo "
                  "de este.", "error")
            return redirect(url_for("perfiles.matriz", perfil_id=perfil_id))

    if conceder and permiso["sensible"] and len(motivo) < 15:
        flash(f"{permiso['codigo']} es un permiso sensible: da acceso a "
              f"agregados de bienestar, a la bitacora o a los parametros de "
              f"privacidad. Escribe el motivo (al menos 15 caracteres) para "
              f"que quede en la bitacora.", "error")
        return redirect(url_for("perfiles.matriz", perfil_id=perfil_id))

    with cursor(commit=True) as cur:
        if conceder:
            cur.execute("INSERT INTO usuarios.perfil_permiso (perfil_id, permiso_id) "
                        "VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (perfil_id, permiso_id))
        else:
            cur.execute("DELETE FROM usuarios.perfil_permiso "
                        " WHERE perfil_id = %s AND permiso_id = %s",
                        (perfil_id, permiso_id))

    # El recurso de la bitácora lleva el motivo cuando lo hay: así la línea
    # se explica sola sin tener que cruzarla con otra tabla.
    detalle = f"{perfil['codigo']}:{permiso['codigo']}"
    if conceder and permiso["sensible"]:
        detalle += f" motivo={motivo[:40]}"
    registrar("PERFIL_MODIFICADO", "EXITO", tipo_recurso="PERFIL", recurso=detalle)

    verbo = "concedido a" if conceder else "retirado de"
    extra = ""
    if conceder:
        extra = (" El cambio surte efecto en la siguiente peticion de cada "
                 "sesion: los permisos no viajan en el token, se consultan "
                 "en la base.")
    flash(f"Permiso {permiso['codigo']} {verbo} {perfil['codigo']}.{extra}", "ok")
    return redirect(url_for("perfiles.matriz", perfil_id=perfil_id))
