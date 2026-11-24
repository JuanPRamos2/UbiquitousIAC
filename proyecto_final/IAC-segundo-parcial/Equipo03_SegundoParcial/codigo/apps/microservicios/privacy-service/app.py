"""
privacy-service — seudonimización y umbral mínimo k.

Puerto 8111. Juan Pablo Ramos (#610248).

Este servicio NO calcula ruido de Laplace y NO descuenta épsilon.
Eso vive en agregado.fn_ruido_laplace, y solo lo llama
agregado.fn_calcular_agregado_protegido (lo usan queries-service y la
semilla). Mezclar el umbral y el ruido en el mismo archivo es lo que
hace imposible contestar en vivo «¿dónde está cada cosa?».

Lo que sí hace este servicio, y se puede señalar con el dedo:

  - lee k_umbral_minimo de agregado.parametro_privacidad;
  - dice si un resultado ya publicado salió como GRUPO_INSUFICIENTE;
  - devuelve el seudónimo de la sesión, nunca el de otra persona;
  - dice en voz alta que esto es seudonimización, no anonimización.

No hace COUNT(*) sobre autoreporte.respuesta. El rol de la aplicación
no puede leer esa tabla: si pudiera contar personas, podría restar dos
consultas y aislar a alguien. El conteo ocurre dentro de la función
protegida, y aquí solo se lee el estado que esa función ya publicó.
"""
import os

from flask import g, request

from comun import (ErrorApi, VERSION_API, crear_servicio, limite_consumo,
                   responder, requiere_permiso, requiere_token)
from comun.datos import consultar_uno, ping as ping_pg
from comun.seguridad import obtener_redis

os.environ.setdefault("NOMBRE_SERVICIO", "privacy-service")


def _ping_redis():
    obtener_redis().ping()


app = crear_servicio(
    "privacy-service",
    "Seudonimizacion y umbral minimo de grupo. No calcula el ruido.",
    comprobaciones={"postgresql": ping_pg, "redis": _ping_redis})

from contrato import montar as _montar_contrato
_montar_contrato(app)

BASE = f"/api/{VERSION_API}/privacidad"


def _k():
    fila = consultar_uno(
        "SELECT valor, unidad, descripcion, justificacion "
        "FROM agregado.parametro_privacidad WHERE clave = 'k_umbral_minimo'")
    if not fila:
        raise ErrorApi("PARAMETRO_AUSENTE",
                       "No esta cargado k_umbral_minimo.", 503)
    return fila


def _numero(valor):
    from decimal import Decimal
    if isinstance(valor, Decimal):
        return int(valor) if valor == valor.to_integral_value() else float(valor)
    return valor


@app.get(f"{BASE}/politica")
@requiere_token
def politica():
    limite_consumo()
    aviso = consultar_uno(
        "SELECT aviso_id, version, explicacion_k, explicacion_dp, "
        "       forma_agregacion, quien_no_accede "
        "FROM consentimiento.aviso_privacidad WHERE vigente "
        "ORDER BY version DESC LIMIT 1")
    if not aviso:
        raise ErrorApi("AVISO_NO_CONFIGURADO", "No hay aviso vigente.", 503)
    k = _k()
    return responder({
        "aviso_id": aviso["aviso_id"],
        "version_aviso": aviso["version"],
        "terminologia": "seudonimizacion",
        "no_es": "anonimizacion",
        "por_que": "La correspondencia persona-seudonimo existe, en una tabla "
                   "que este servicio no lee. Por eso no se dice que la "
                   "respuesta sea anonima.",
        "k": _numero(k["valor"]),
        "unidad_k": k["unidad"],
        "explicacion_k": aviso["explicacion_k"],
        "explicacion_del_ruido": aviso["explicacion_dp"],
        "forma_agregacion": aviso["forma_agregacion"],
        "quien_no_accede": aviso["quien_no_accede"],
        "donde_se_calcula_el_ruido":
            "agregado.fn_ruido_laplace, llamada solo desde "
            "agregado.fn_calcular_agregado_protegido",
        "que_hace_este_servicio":
            "Publica el umbral k y el seudonimo de la sesion. No suma ruido "
            "y no descuenta epsilon.",
    }, raiz="politica_respuesta")


@app.get(f"{BASE}/umbral")
@requiere_permiso("AGREGADO_UNIDAD", "AGREGADO_GLOBAL", "PARAMETRO_ADMIN")
def umbral():
    limite_consumo()
    k = _k()
    return responder({
        "clave": "k_umbral_minimo",
        "k": _numero(k["valor"]),
        "unidad": k["unidad"],
        "descripcion": k["descripcion"],
        "justificacion": k["justificacion"],
        "que_pasa_si_el_grupo_es_menor":
            "El resultado se publica como GRUPO_INSUFICIENTE, sin valor. "
            "Este servicio no revela el n exacto: restarlo de otra consulta "
            "serviria para aislar a una persona.",
    }, raiz="umbral_respuesta")


@app.get(f"{BASE}/seudonimo")
@requiere_permiso("PARTICIPACION_PROPIA", "CONSENT_HISTORIAL_PROPIO")
def seudonimo_propio():
    limite_consumo()
    fila = consultar_uno(
        "SELECT seudonimo_id FROM portal.v_participacion_propia WHERE usuario_id = %s",
        (g.actor.get("sub"),))
    if not fila:
        raise ErrorApi("SIN_SEUDONIMO",
                       "Esta cuenta no tiene seudonimo operativo.", 403)
    return responder({
        "seudonimo_id": fila["seudonimo_id"],
        "es_el_de_la_sesion": True,
        "permite_reidentificar": False,
        "nota": "Conocer el propio seudonimo no abre la tabla que lo une "
                "con el empleado. Esa tabla no la lee este servicio.",
    }, raiz="seudonimo_respuesta")


@app.get(f"{BASE}/publicacion")
@requiere_permiso("AGREGADO_UNIDAD", "AGREGADO_GLOBAL")
def publicacion():
    """Dice si el grupo ya publicado alcanzó k. No recalcula y no gasta épsilon."""
    limite_consumo()
    unidad = (request.args.get("unidad_organizacional_id") or "").strip()
    campania = (request.args.get("campania_id") or "").strip()
    if not unidad or not campania:
        raise ErrorApi(
            "PARAMETRO_INVALIDO",
            "Hacen falta unidad_organizacional_id y campania_id.", 400)

    if "AGREGADO_GLOBAL" not in g.permisos:
        alcance = consultar_uno(
            "SELECT unidad_alcance_id FROM usuarios.usuario_perfil "
            "WHERE usuario_id = %s AND perfil_id = %s",
            (g.actor.get("sub"), g.actor.get("perfil_id")))
        propia = (alcance or {}).get("unidad_alcance_id")
        if not propia or propia != unidad:
            raise ErrorApi(
                "FUERA_DE_ALCANCE",
                "Sin alcance global solo puedes consultar tu unidad.", 403)

    filas = consultar_uno(
        "SELECT estado_publicacion FROM agregado.v_tablero_unidad "
        "WHERE unidad_organizacional_id = %s AND campania_id = %s "
        "ORDER BY estado_publicacion LIMIT 1",
        (unidad, campania))
    k = _numero(_k()["valor"])
    if not filas:
        return responder({
            "unidad_organizacional_id": unidad,
            "campania_id": campania,
            "k": k,
            "estado": "SIN_PUBLICACION",
            "publicable": False,
            "n_exacto": None,
            "motivo": "Todavia no hay un resultado publicado para esa "
                      "combinacion. Este servicio no cuenta respuestas "
                      "crudas para no abrir esa tabla.",
        }, raiz="publicacion_respuesta")

    estado = filas["estado_publicacion"]
    return responder({
        "unidad_organizacional_id": unidad,
        "campania_id": campania,
        "k": k,
        "estado": estado,
        "publicable": estado == "PUBLICADO",
        "n_exacto": None,
        "motivo": {
            "PUBLICADO": "El grupo alcanzo k cuando se calculo el agregado.",
            "GRUPO_INSUFICIENTE": "Habia menos de k respuestas. No hay valor.",
            "PRESUPUESTO_PRIVACIDAD_AGOTADO":
                "El grupo pudo ser suficiente, pero ya no se publican valores "
                "nuevos porque se agoto el presupuesto. Eso lo administra "
                "configuration-service y la funcion de agregado, no este servicio.",
        }.get(estado, estado),
    }, raiz="publicacion_respuesta")
