"""
Preferencias de notificación y cola de envío push.

LAS DOS COSAS QUE FALTABAN
--------------------------
La especificación del servicio pide «notificaciones internas y push […];
preferencias; […] evitando revelar información sensible». El servicio solo
tenía la bandeja interna: no había preferencias ni push.

POR QUÉ EL TEXTO DEL PUSH ES MÁS VAGO QUE EL DE LA BANDEJA
----------------------------------------------------------
Esta es la decisión que más importa de todo el módulo, y no es obvia.

Una notificación de la bandeja se lee DENTRO de la aplicación, después de
que la persona se autenticó. Una notificación push se dibuja en la
**pantalla bloqueada del teléfono**, donde la ve cualquiera que esté cerca:
el compañero de al lado, quien va junto en el camión, quien tome el
teléfono de la mesa.

En una plataforma de bienestar laboral eso tiene consecuencias reales. Un
push que diga «Te falta responder la encuesta de clima de Call Center
Turno B» le dice a quien esté mirando que esa persona trabaja ahí y que
está en un programa de bienestar. Un push que diga «Se detectó una
condición en tu unidad» es peor todavía.

Por eso el push NO lleva el mensaje de la bandeja. Lleva un texto genérico
por tipo, pensado para leerse de lejos sin revelar nada, y la información
real espera del otro lado de la autenticación. El costo es que la persona
tiene que abrir la aplicación para saber de qué se trata; es exactamente
el intercambio que se quiere.

POR QUÉ ESTE SERVICIO NO HABLA CON FIREBASE
--------------------------------------------
Este módulo decide QUIÉN debe recibir un push y lo deja en una cola. La
entrega a FCM o APNs la hace un repartidor aparte, que es el único
componente que necesita las credenciales del proveedor.

Es una separación deliberada y no una tarea pendiente: meter las
credenciales de Firebase en el servicio que además lee la base de
notificaciones significa que cualquier fallo en este servicio expone esas
credenciales, y que no se puede reintentar un envío fallido sin volver a
tocar la base. La cola tiene estado e intentos justamente para que el
repartidor pueda reintentar sin ayuda de nadie.
"""
import datetime as dt

# Texto que se muestra en la pantalla bloqueada. Deliberadamente vago.
# Ver el encabezado del módulo: esto lo ve cualquiera que esté cerca.
TEXTO_PUSH = {
    "CAMPANIA_ABIERTA":        "Tienes algo nuevo en Bienestar Nexum",
    "RECORDATORIO_ENCUESTA":   "Tienes algo pendiente en Bienestar Nexum",
    "CONDICION_DETECTADA":     "Tienes algo nuevo en Bienestar Nexum",
    "PLAN_APROBADO":           "Tienes algo nuevo en Bienestar Nexum",
    "CONSENTIMIENTO_POR_VENCER": "Tienes algo pendiente en Bienestar Nexum",
    "SOLICITUD_APOYO_ACTUALIZADA": "Tienes algo nuevo en Bienestar Nexum",
    "CONFIRMACION_RECIBIDA":   "Tienes algo nuevo en Bienestar Nexum",
}

# Por omisión: todo en la bandeja, nada por push.
#
# El valor por omisión importa tanto como la opción. Si el push viniera
# encendido, la primera notificación llegaría a la pantalla bloqueada de
# alguien que nunca eligió eso, y para entonces ya pasó. Que lo encienda
# quien lo quiera.
PREFERENCIAS_POR_OMISION = {
    "bandeja": True,
    "push": False,
    "tipos_silenciados": [],
    # Horas en las que no se encola push, en hora local del usuario. Un
    # recordatorio de encuesta a las 2 de la mañana no es un recordatorio,
    # es una molestia, y en una plataforma de bienestar laboral molestar
    # fuera del horario es contradecir el propósito.
    "silencio_desde": 21,
    "silencio_hasta": 7,
}


def normalizar(crudas):
    """Mezcla lo que el usuario guardó con los valores por omisión.

    Se mezcla en lugar de exigir el objeto completo: así agregar una
    preferencia nueva en el futuro no deja a los usuarios existentes con
    un campo ausente que el código tendría que tratar como un caso raro.
    """
    preferencias = dict(PREFERENCIAS_POR_OMISION)
    preferencias.update({k: v for k, v in (crudas or {}).items()
                         if k in PREFERENCIAS_POR_OMISION})
    preferencias["tipos_silenciados"] = sorted(
        {str(t).upper() for t in (preferencias.get("tipos_silenciados") or [])})
    for clave in ("silencio_desde", "silencio_hasta"):
        try:
            preferencias[clave] = max(0, min(23, int(preferencias[clave])))
        except (TypeError, ValueError):
            preferencias[clave] = PREFERENCIAS_POR_OMISION[clave]
    preferencias["bandeja"] = bool(preferencias.get("bandeja", True))
    preferencias["push"] = bool(preferencias.get("push", False))
    return preferencias


def validar(crudas):
    """Devuelve la lista de problemas. Vacía si todo está bien."""
    problemas = []
    if not isinstance(crudas, dict):
        return [{"campo": "preferencias", "problema": "debe ser un objeto"}]

    desconocidas = set(crudas) - set(PREFERENCIAS_POR_OMISION)
    if desconocidas:
        # Se rechaza en lugar de ignorar: alguien que manda «notificaciones»
        # en vez de «bandeja» cree que guardó algo y no guardó nada.
        problemas.append({
            "campo": "preferencias",
            "problema": f"campos desconocidos: {', '.join(sorted(desconocidas))}; "
                        f"validos: {', '.join(sorted(PREFERENCIAS_POR_OMISION))}"})

    tipos = crudas.get("tipos_silenciados")
    if tipos is not None and not isinstance(tipos, list):
        problemas.append({"campo": "tipos_silenciados",
                          "problema": "debe ser una lista de tipos"})

    for clave in ("silencio_desde", "silencio_hasta"):
        if clave in crudas:
            try:
                hora = int(crudas[clave])
            except (TypeError, ValueError):
                problemas.append({"campo": clave, "problema": "debe ser una hora 0-23"})
                continue
            if not 0 <= hora <= 23:
                problemas.append({"campo": clave, "problema": "fuera de 0-23"})
    return problemas


def en_silencio(preferencias, ahora=None):
    """Si la hora actual cae dentro de la franja de silencio.

    La franja cruza la medianoche en el caso normal (21 a 7), así que la
    comparación no puede ser un simple «entre». Con `desde < hasta` la
    franja es del mismo día; con `desde > hasta` cruza.
    """
    ahora = ahora or dt.datetime.now()
    hora = ahora.hour
    desde = preferencias.get("silencio_desde", 21)
    hasta = preferencias.get("silencio_hasta", 7)
    if desde == hasta:
        return False
    if desde < hasta:
        return desde <= hora < hasta
    return hora >= desde or hora < hasta


def debe_encolar_push(preferencias, tipo, ahora=None):
    """Tres condiciones, y las tres tienen que cumplirse."""
    if not preferencias.get("push"):
        return False, "el usuario no activo el push"
    if tipo in (preferencias.get("tipos_silenciados") or []):
        return False, f"el usuario silencio el tipo {tipo}"
    if en_silencio(preferencias, ahora):
        return False, "esta dentro de la franja de silencio del usuario"
    return True, ""


def sobre_push(notificacion, dispositivos):
    """Arma lo que se encola para el repartidor.

    Nótese lo que NO lleva: ni el mensaje de la bandeja, ni la unidad, ni
    la campaña. Solo el texto genérico del tipo y el identificador de la
    notificación, para que la aplicación la abra DESPUÉS de autenticar.
    """
    tipo = notificacion["tipo"]
    return {
        "push_id": f"PSH-{notificacion['notificacion_id'][4:]}",
        "notificacion_id": notificacion["notificacion_id"],
        "destinatario_usuario_id": notificacion["destinatario_usuario_id"],
        "dispositivos": list(dispositivos),
        # El texto que se ve en la pantalla bloqueada.
        "titulo": "Bienestar Nexum",
        "cuerpo": TEXTO_PUSH.get(tipo, "Tienes algo nuevo en Bienestar Nexum"),
        # El tipo viaja como dato, NO como texto visible: la aplicación lo
        # usa para saber a qué pantalla llevar, y nunca se dibuja.
        "datos": {"notificacion_id": notificacion["notificacion_id"]},
        "estado": "PENDIENTE",
        "intentos": 0,
        "fecha_encolado": dt.datetime.now(dt.timezone.utc),
    }
