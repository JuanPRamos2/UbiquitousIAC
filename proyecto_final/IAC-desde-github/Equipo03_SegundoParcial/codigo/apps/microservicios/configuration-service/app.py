"""
configuration-service — gobierno de los parámetros del sistema.

QUÉ PROBLEMA RESUELVE
---------------------
El umbral k, los presupuestos de épsilon y la tolerancia de error viven en
`agregado.parametro_privacidad` desde el esquema base, y los lee
`agregado.fn_parametro`. Lo que no existía era un camino para CAMBIARLOS.

El efecto de no tenerlo no era que no se pudieran cambiar: era que se
cambiaban con un UPDATE suelto. Y un UPDATE pisa el valor anterior. El
umbral k es la afirmación central del proyecto —«ningún resultado permite
llegar a una persona»— y se podía bajar de 5 a 2 sin justificación, sin
que quedara el valor viejo y sin que nadie pudiera reconstruir después con
qué umbral se publicó cada campaña.

LAS CUATRO DECISIONES
---------------------
1. **El servicio no hace el UPDATE.** Llama a
   `configuracion.fn_cambiar_parametro`, que es SECURITY DEFINER y escribe
   el historial en la MISMA transacción. El rol de la aplicación no tiene
   UPDATE sobre `parametro_privacidad`, así que no existe un segundo
   camino. Un historial que se puede evitar no es un historial.

2. **Los límites están en la base, no aquí.** El piso del umbral k vive en
   `configuracion.limite_parametro`. Una validación en Python la salta
   cualquiera con acceso a `psql`, y la afirmación del proyecto no puede
   depender de que nadie lo haga.

3. **Hay parámetros congelados mientras una campaña esté abierta.**
   Cambiar el umbral a mitad de una medición produce un tablero donde unas
   unidades se publicaron con un criterio y otras con otro, sin que nada
   en la pantalla lo diga. El servicio no lo decide: lo decide la columna
   `congelar_en_campania_abierta`, y la función lo hace cumplir.

4. **Leer no exige el permiso de cambiar.** Quien ve un tablero tiene
   derecho a saber con qué umbral se publicó. Esconder los parámetros no
   protege a nadie: lo que protege es el ruido y el umbral, no el secreto
   sobre sus valores. Esto es privacidad diferencial, no seguridad por
   oscuridad.
"""
import datetime as dt
import os

import psycopg2
from psycopg2 import errorcodes
from flask import g

from comun import (ErrorApi, VERSION_API, crear_servicio, cuerpo_peticion,
                   limite_consumo, obtener_redis, responder,
                   requiere_permiso, requiere_token)
from comun.datos import consultar, consultar_uno, cursor, ping as ping_pg

os.environ.setdefault("NOMBRE_SERVICIO", "configuration-service")

# Los códigos SQLSTATE con los que `fn_cambiar_parametro` distingue sus
# rechazos, traducidos al sobre de error del sistema. Sin esta traducción
# los cuatro rechazos saldrían como un 500 genérico y quien los recibiera
# no sabría si pedir otro valor, esperar a que cierre la campaña o
# escribir una justificación más larga.
#
# Las claves se toman de `psycopg2.errorcodes` y no se escriben a mano.
# `Error.pgcode` trae el SQLSTATE de cinco caracteres ('23514'), no el
# nombre simbólico ('check_violation'), y un diccionario con los nombres
# simbólicos no acierta NUNCA: cae siempre al caso por omisión, así que
# los cuatro rechazos salen con el mismo código genérico y el cliente
# pierde justo la información que esta traducción existe para darle. Pasó,
# y lo descubrió la prueba que esperaba FUERA_DE_LIMITE.
TRADUCCION = {
    errorcodes.NO_DATA_FOUND: ("PARAMETRO_NO_EXISTE", 404),
    errorcodes.CHECK_VIOLATION: ("FUERA_DE_LIMITE", 422),
    errorcodes.OBJECT_NOT_IN_PREREQUISITE_STATE: ("CAMPANIA_ABIERTA", 409),
    errorcodes.RAISE_EXCEPTION: ("PARAMETRO_SIN_LIMITES", 422),
}


def _ping_redis():
    obtener_redis().ping()


app = crear_servicio(
    "configuration-service",
    "Gobierno de los parametros del sistema: umbrales, presupuestos de "
    "privacidad y limites por perfil",
    comprobaciones={"postgresql": ping_pg, "redis": _ping_redis})

from contrato import montar as _montar_contrato  # noqa: E402
_montar_contrato(app)

BASE = f"/api/{VERSION_API}/configuracion"


def _bitacora(accion, resultado, recurso=None):
    try:
        with cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO auditoria.bitacora (actor_usuario_id, actor_perfil, "
                " accion, tipo_recurso, recurso_id, resultado, correlacion_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                ((g.get("actor") or {}).get("sub"),
                 ((g.get("actor") or {}).get("perfil") or "ANONIMO")[:30],
                 accion, "PARAMETRO", str(recurso) if recurso else None,
                 resultado, getattr(g, "correlacion_id", "")))
    except Exception:
        app.logger.error("No se pudo escribir en la bitacora: %s", accion)


def _numero(valor):
    return float(valor) if valor is not None else None


def _serializable(fila):
    salida = {}
    for clave, valor in dict(fila).items():
        if isinstance(valor, (dt.date, dt.datetime)):
            salida[clave] = valor.isoformat()
        elif hasattr(valor, "quantize"):
            salida[clave] = float(valor)
        else:
            salida[clave] = valor
    return salida


# =========================================================================
# Leer los parámetros
# =========================================================================
@app.get(f"{BASE}/parametros")
@requiere_permiso("PARAMETRO_ADMIN", "AGREGADO_GLOBAL", "AGREGADO_UNIDAD",
                  "BITACORA_CONSULTAR")
def parametros():
    """Los parámetros vigentes, con su límite y su justificación.

    Leer NO exige el permiso de cambiar. Quien ve un tablero tiene derecho
    a saber con qué umbral se publicó: esconder el valor de k no protege a
    nadie, porque lo que protege es el umbral mismo y el ruido, no el
    secreto sobre su valor. Esto es privacidad diferencial, no seguridad
    por oscuridad.
    """
    limite_consumo(maximo=120)
    filas = consultar(
        "SELECT p.clave, p.valor, p.unidad, p.descripcion, p.justificacion, "
        "       p.actualizado_por, p.fecha_actualizacion, "
        "       l.minimo, l.maximo, l.congelar_en_campania_abierta, "
        "       l.motivo AS motivo_limite "
        "  FROM agregado.parametro_privacidad p "
        "  LEFT JOIN configuracion.limite_parametro l USING (clave) "
        " ORDER BY p.clave")

    abiertas = [f["campania_id"] for f in consultar(
        "SELECT campania_id FROM catalogo.campania WHERE estado = 'ABIERTA' "
        " ORDER BY campania_id")]

    datos = []
    for fila in filas:
        d = _serializable(fila)
        # Se dice, por parámetro, si AHORA MISMO se puede cambiar y por
        # qué no. Un cliente que tenga que deducirlo cruzando la lista de
        # campañas abiertas con una columna booleana lo va a deducir mal.
        if d.get("minimo") is None and d.get("maximo") is None:
            d["modificable"] = False
            d["motivo_no_modificable"] = (
                "No tiene limites declarados en configuracion."
                "limite_parametro. Agregar un parametro nuevo no lo deja "
                "modificable por omision: eso lo dejaria sin proteccion sin "
                "que nadie lo hubiera decidido.")
        elif d.get("congelar_en_campania_abierta") and abiertas:
            d["modificable"] = False
            d["motivo_no_modificable"] = (
                f"Congelado mientras haya una campania abierta "
                f"({', '.join(abiertas)}).")
        else:
            d["modificable"] = True
        datos.append(d)

    return responder({
        "parametros": datos,
        "total": len(datos),
        "campanias_abiertas": abiertas,
        "nota": "El unico camino para cambiar un valor es PATCH sobre este "
                "servicio, que llama a configuracion.fn_cambiar_parametro. "
                "El rol de la aplicacion no tiene UPDATE sobre "
                "agregado.parametro_privacidad, asi que no hay un segundo "
                "camino sin historial.",
    }, 200, raiz="parametros_respuesta")


@app.get(f"{BASE}/parametros/<clave>")
@requiere_permiso("PARAMETRO_ADMIN", "AGREGADO_GLOBAL", "AGREGADO_UNIDAD",
                  "BITACORA_CONSULTAR")
def parametro(clave):
    """Un parámetro con su historial completo de cambios."""
    limite_consumo(maximo=120)
    fila = consultar_uno(
        "SELECT p.clave, p.valor, p.unidad, p.descripcion, p.justificacion, "
        "       p.actualizado_por, p.fecha_actualizacion, "
        "       l.minimo, l.maximo, l.congelar_en_campania_abierta, "
        "       l.motivo AS motivo_limite "
        "  FROM agregado.parametro_privacidad p "
        "  LEFT JOIN configuracion.limite_parametro l USING (clave) "
        " WHERE p.clave = %s", (clave,))
    if not fila:
        raise ErrorApi("PARAMETRO_NO_EXISTE",
                       f"No existe el parametro '{clave}'.", 404)

    historial = consultar(
        "SELECT cambio_id, valor_anterior, valor_nuevo, justificacion, "
        "       actor_usuario_id, campanias_abiertas, fecha_cambio "
        "  FROM configuracion.cambio_parametro WHERE clave = %s "
        " ORDER BY fecha_cambio DESC", (clave,))

    datos = _serializable(fila)
    datos["historial"] = [_serializable(h) for h in historial]
    datos["nota_historial"] = (
        "Cada fila trae el valor ANTERIOR y las campanias que estaban "
        "abiertas en ese momento. Sin el valor anterior no se puede "
        "reconstruir con que umbral se publico cada campania, que es para "
        "lo unico que existiria el historial."
        if historial else
        "Sin cambios registrados: el valor es el que se sembro al crear la "
        "base.")
    return responder(datos, 200, raiz="parametro_respuesta")


# =========================================================================
# Cambiar un parámetro
# =========================================================================
@app.patch(f"{BASE}/parametros/<clave>")
@requiere_permiso("PARAMETRO_ADMIN")
def cambiar(clave):
    """Cambia un parámetro llamando a la función que escribe el historial.

    El servicio NO hace el UPDATE. Si lo hiciera en dos sentencias —una
    para el valor y otra para el historial—, un error entre ellas dejaría
    el umbral cambiado sin fila de historial, que es el caso exacto que
    vuelve inútil un historial. La función lo hace en una transacción.
    """
    limite_consumo(maximo=20)
    cuerpo = cuerpo_peticion()

    valor = cuerpo.get("valor")
    justificacion = (cuerpo.get("justificacion") or "").strip()

    problemas = []
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        problemas.append({"campo": "valor", "problema": "numero requerido"})
    if len(justificacion) < 30:
        problemas.append({
            "campo": "justificacion",
            "problema": "al menos 30 caracteres. Un cambio al umbral k sin "
                        "motivo escrito es exactamente el cambio que nadie "
                        "quiere tener que explicar seis meses despues"})
    if problemas:
        raise ErrorApi("VALIDACION", "La solicitud tiene campos invalidos.",
                       422, problemas)

    actor = (g.get("actor") or {}).get("sub")
    try:
        with cursor(commit=True) as cur:
            cur.execute(
                "SELECT valor_anterior, valor_nuevo, cambio_id "
                "  FROM configuracion.fn_cambiar_parametro(%s,%s,%s,%s,%s)",
                (clave, valor, justificacion, actor,
                 getattr(g, "correlacion_id", None)))
            resultado = cur.fetchone()
    except psycopg2.Error as error:
        # La función distingue sus rechazos por SQLSTATE. Traducirlos es lo
        # que permite al cliente saber qué hacer: pedir otro valor, esperar
        # a que cierre la campaña o escribir más justificación.
        codigo, http = TRADUCCION.get(error.pgcode,
                                      ("ERROR_DE_CONFIGURACION", 422))
        mensaje = (getattr(error, "diag", None)
                   and error.diag.message_primary) or str(error)
        # El prefijo «CODIGO: » del RAISE se quita: ya viaja en el campo
        # `codigo` del sobre y repetirlo dentro del mensaje se lee como un
        # error del sistema y no como una regla.
        if ":" in mensaje and mensaje.split(":", 1)[0].isupper():
            mensaje = mensaje.split(":", 1)[1].strip()
        _bitacora("PARAMETRO_CAMBIADO", "RECHAZADO", clave)
        raise ErrorApi(codigo, mensaje, http,
                       [{"campo": "clave", "problema": clave},
                        {"campo": "valor", "problema": str(valor)}])

    _bitacora("PARAMETRO_CAMBIADO", "EXITO", clave)
    return responder({
        "clave": clave,
        "valor_anterior": _numero(resultado["valor_anterior"]),
        "valor_nuevo": _numero(resultado["valor_nuevo"]),
        "cambio_id": resultado["cambio_id"],
        "nota": "El cambio NO vuelve a publicar nada. Los agregados ya "
                "publicados guardan el valor y el ruido que se les aplico "
                "en su momento, con el k que regia entonces: cambiar el "
                "umbral ahora no republica un grupo que se suprimio antes, "
                "y por eso el historial es lo unico que permite saber con "
                "que criterio se publico cada campania.",
    }, 200, raiz="parametro_cambiado")


# =========================================================================
# Límites por perfil
# =========================================================================
@app.get(f"{BASE}/limites-perfil")
@requiere_permiso("PARAMETRO_ADMIN", "USUARIO_ADMIN", "BITACORA_CONSULTAR")
def limites_perfil():
    """Los topes de consulta por perfil, con el motivo de cada uno.

    Existen porque los topes estaban escritos como constantes dentro de
    cada servicio. Con eso, un auditor que revisa mil registros y un
    colaborador que mira su propia participación tenían el mismo tope, y
    el único modo de cambiarlo era volver a desplegar.
    """
    limite_consumo(maximo=120)
    filas = consultar(
        "SELECT pf.codigo AS perfil, lp.recurso, lp.maximo_por_hora, lp.motivo "
        "  FROM configuracion.limite_perfil lp "
        "  JOIN usuarios.perfil pf USING (perfil_id) "
        " ORDER BY lp.recurso, lp.maximo_por_hora DESC")
    return responder({
        "limites": [_serializable(f) for f in filas],
        "total": len(filas),
        "nota": "Son topes por hora y por perfil. Un tope bajo para el "
                "auditor no protegeria nada y convertiria la auditoria en "
                "algo que no se puede hacer; un tope alto para el "
                "colaborador no le sirve, porque solo consulta lo propio.",
    }, 200, raiz="limites_respuesta")


@app.get(f"{BASE}/mis-limites")
@requiere_token
def mis_limites():
    """Los topes que aplican a quien pregunta.

    Pide token pero ningún permiso en particular, y es deliberado: saber
    cuántas consultas te quedan no revela nada de nadie, y un cliente que
    no lo sabe reintenta en bucle contra un 429 —que es justo lo que el
    límite venía a evitar.
    """
    limite_consumo(maximo=120)
    perfil_id = (g.get("actor") or {}).get("perfil_id")
    filas = consultar(
        "SELECT recurso, maximo_por_hora, motivo "
        "  FROM configuracion.limite_perfil WHERE perfil_id = %s "
        " ORDER BY recurso", (perfil_id,))
    return responder({
        "perfil": (g.get("actor") or {}).get("perfil"),
        "limites": [_serializable(f) for f in filas],
        "nota": "Si la lista viene vacia, este perfil no tiene topes "
                "declarados y rige el del servicio que se consulte."
                if not filas else
                "Son topes por hora. El servicio que se consulte puede "
                "tener el suyo, mas bajo, para una operacion concreta.",
    }, 200, raiz="mis_limites_respuesta")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PUERTO", "8122")))
