"""
Preferencias de notificación y cola de push.

La especificación del servicio pide «notificaciones internas y push […];
preferencias; […] evitando revelar información sensible». El servicio solo
tenía la bandeja interna.

LA PRUEBA QUE MÁS IMPORTA
-------------------------
`test_el_push_no_revela_de_que_se_trata`. Una notificación de la bandeja se
lee dentro de la aplicación, después de autenticarse. Una push se dibuja en
la **pantalla bloqueada**, donde la ve cualquiera que esté cerca.

En una plataforma de bienestar laboral eso tiene consecuencias: un push que
diga «Te falta responder la encuesta de Call Center Turno B» le dice a
quien esté mirando que esa persona trabaja ahí y que está en un programa de
bienestar. Por eso el push lleva un texto genérico y la información real
espera del otro lado de la autenticación.
"""
import datetime as dt
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVICIO = os.path.join(RAIZ, "apps", "microservicios", "notifications-service")
sys.path.insert(0, SERVICIO)

import preferencias as prefs  # noqa: E402


# =========================================================================
# Valores por omisión
# =========================================================================

def test_el_push_viene_apagado_por_omision():
    """Si viniera encendido, el primer aviso llega a una pantalla bloqueada
    de alguien que nunca eligió eso, y para entonces ya pasó."""
    p = prefs.normalizar(None)
    assert p["push"] is False
    assert p["bandeja"] is True
    assert p["tipos_silenciados"] == []


def test_guardar_una_preferencia_no_borra_las_demas():
    """Se mezcla con los valores por omisión en lugar de exigir el objeto
    completo: agregar una preferencia nueva después no deja a los usuarios
    existentes con un campo ausente."""
    p = prefs.normalizar({"push": True})
    assert p["push"] is True
    assert p["bandeja"] is True            # no se perdió
    assert p["silencio_desde"] == 21


def test_un_campo_desconocido_se_rechaza_en_vez_de_ignorarse():
    """Quien manda «notificaciones» en vez de «bandeja» cree que guardó."""
    problemas = prefs.validar({"notificaciones": True})
    assert problemas
    assert "desconocidos" in problemas[0]["problema"]


@pytest.mark.parametrize("hora_mala", [-1, 24, 99, "tarde", None])
def test_una_hora_de_silencio_invalida_se_rechaza(hora_mala):
    assert prefs.validar({"silencio_desde": hora_mala})


# =========================================================================
# El texto que se ve en la pantalla bloqueada
# =========================================================================

def test_el_push_no_revela_de_que_se_trata():
    """La prueba central de este módulo.

    Se arma un push para una notificación cuyo mensaje nombra la unidad, y
    se comprueba que NADA de eso aparece en lo que el teléfono va a
    dibujar.
    """
    notificacion = {
        "notificacion_id": "NTF-0123456789AB",
        "destinatario_usuario_id": "USR-00001",
        "tipo": "RECORDATORIO_ENCUESTA",
        "titulo": "Te falta responder la campania de Call Center Turno B",
        "mensaje": "La campania de clima de Call Center - Turno B cierra el "
                   "viernes y todavia no registramos tu respuesta.",
        "unidad_organizacional_id": "UO-CC-TURNO-B",
        "campania_id": "CAMP-2026-S5",
    }
    sobre = prefs.sobre_push(notificacion, ["token-de-prueba-0123456789"])

    visible = f"{sobre['titulo']} {sobre['cuerpo']}".lower()
    for filtracion in ("call center", "turno b", "uo-cc", "camp-2026",
                       "encuesta", "campania", "clima", "respuesta"):
        assert filtracion not in visible, (
            f"El push muestra «{filtracion}» en la pantalla bloqueada, donde "
            f"lo ve cualquiera que este cerca.")

    # Y tampoco va escondido en los datos, salvo el identificador que la
    # aplicación necesita para abrir la pantalla DESPUÉS de autenticar.
    assert set(sobre["datos"]) == {"notificacion_id"}
    assert sobre["datos"]["notificacion_id"] == "NTF-0123456789AB"
    assert "mensaje" not in sobre and "unidad_organizacional_id" not in sobre


def test_todos_los_tipos_tienen_un_texto_generico():
    """Un tipo sin texto caería en el genérico; conviene que sea a propósito
    y no por olvido, así que se comprueba que estén todos."""
    fuente = open(os.path.join(SERVICIO, "app.py"), encoding="utf-8").read()
    bloque = fuente[fuente.index("TIPOS = {"):fuente.index("# Una notificacion con")]
    tipos = {linea.split('"')[1] for linea in bloque.splitlines()
             if linea.strip().startswith('"')}
    faltan = tipos - set(prefs.TEXTO_PUSH)
    assert not faltan, f"Tipos sin texto de push definido: {sorted(faltan)}"


# =========================================================================
# Cuándo se encola
# =========================================================================

def test_sin_push_activado_no_se_encola():
    quiere, motivo = prefs.debe_encolar_push(
        prefs.normalizar({"push": False}), "CAMPANIA_ABIERTA")
    assert quiere is False
    assert "no activo" in motivo


def test_un_tipo_silenciado_no_se_encola():
    p = prefs.normalizar({"push": True,
                          "tipos_silenciados": ["RECORDATORIO_ENCUESTA"]})
    quiere, motivo = prefs.debe_encolar_push(p, "RECORDATORIO_ENCUESTA",
                                             dt.datetime(2026, 11, 4, 12))
    assert quiere is False
    assert "silencio" in motivo
    # Otro tipo sí pasa.
    assert prefs.debe_encolar_push(p, "CAMPANIA_ABIERTA",
                                   dt.datetime(2026, 11, 4, 12))[0] is True


def test_la_franja_de_silencio_cruza_la_medianoche():
    """De 21 a 7 no es «entre 21 y 7»: la comparación simple fallaría.

    Un recordatorio a las 2 de la mañana no es un recordatorio, es una
    molestia, y en una plataforma de bienestar laboral molestar fuera del
    horario contradice el propósito.
    """
    p = prefs.normalizar({"push": True, "silencio_desde": 21, "silencio_hasta": 7})
    for hora in (21, 23, 0, 2, 6):
        assert prefs.en_silencio(p, dt.datetime(2026, 11, 4, hora)), \
            f"las {hora} deberian caer en silencio"
    for hora in (7, 9, 14, 20):
        assert not prefs.en_silencio(p, dt.datetime(2026, 11, 4, hora)), \
            f"las {hora} NO deberian caer en silencio"


def test_una_franja_vacia_no_silencia_nunca():
    p = prefs.normalizar({"silencio_desde": 8, "silencio_hasta": 8})
    assert prefs.en_silencio(p, dt.datetime(2026, 11, 4, 8)) is False


# =========================================================================
# El servicio lo expone
# =========================================================================

def test_el_servicio_expone_preferencias_dispositivos_y_cola():
    fuente = open(os.path.join(SERVICIO, "app.py"), encoding="utf-8").read()
    for ruta in ("/preferencias", "/dispositivos", "/push/pendientes",
                 "/push/<push_id>"):
        assert ruta in fuente, f"falta el endpoint {ruta}"


def test_el_usuario_sale_del_token_y_no_del_cuerpo():
    """Si saliera del cuerpo, cualquiera podría apagarle los avisos a otro."""
    fuente = open(os.path.join(SERVICIO, "app.py"), encoding="utf-8").read()
    bloque = fuente[fuente.index("def guardar_preferencias"):]
    bloque = bloque[:bloque.index("@app.")]
    assert '(g.actor or {}).get("sub")' in bloque
    assert 'cuerpo.get("usuario_id")' not in bloque


def test_hay_tipos_que_el_usuario_no_puede_silenciarse():
    """Un aviso de consentimiento por vencer es una obligación del programa
    hacia la persona, no una cortesía."""
    fuente = open(os.path.join(SERVICIO, "app.py"), encoding="utf-8").read()
    assert "OBLIGATORIOS" in fuente
    assert "CONSENTIMIENTO_POR_VENCER" in fuente[fuente.index("OBLIGATORIOS"):
                                                 fuente.index("OBLIGATORIOS") + 400]


def test_el_servicio_no_habla_con_firebase():
    """Decide quién debe recibir y encola; la entrega es de otro componente.

    Meter las credenciales del proveedor en el servicio que además lee la
    base de notificaciones significa que cualquier fallo aquí las expone.
    """
    fuente = open(os.path.join(SERVICIO, "app.py"), encoding="utf-8").read()
    # Se buscan USOS, no la palabra: el modulo explica por escrito que no
    # habla con Firebase, y una busqueda del nombre se dispararia con esa
    # misma explicacion.
    import re as _re
    usos = [
        r"import\s+firebase", r"from\s+firebase", r"import\s+pyfcm",
        r"https?://fcm\.googleapis", r"https?://.*\.push\.apple\.com",
        r"FIREBASE_[A-Z_]*\s*=", r"FCM_[A-Z_]*\s*=",
    ]
    encontrados = [u for u in usos if _re.search(u, fuente, _re.I)]
    assert not encontrados, (
        f"El servicio esta hablando con un proveedor de push: {encontrados}. "
        f"Las credenciales del proveedor no deben vivir en el servicio que "
        f"ademas lee la base de notificaciones.")
