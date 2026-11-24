"""
Pruebas de la aplicación móvil Android.

EL PROBLEMA, Y CÓMO SE RESUELVE AQUÍ
------------------------------------
El proyecto Android no se puede compilar en este ambiente: Gradle necesita
bajar las dependencias de Maven Central y de dl.google.com, y las dos están
bloqueadas (se comprobó: CONNECT rechazado). Eso está declarado como
limitación, igual que la ausencia de Docker y de MongoDB.

Lo que NO puede quedar sin verificar es lo que suele estar mal: que los
endpoints, los campos y los códigos de error contra los que la aplicación
está escrita existan de verdad y se llamen así. La aplicación de escritorio
acaba de demostrar por qué: validar sus respuestas contra el XSD destapó
seis defectos de contrato que llevaban ahí desde el principio.

Entonces estas pruebas hacen dos cosas:

  1. LEEN el código Kotlin y extraen de él las rutas, los campos JSON y los
     códigos de error que usa. No hay una lista escrita a mano: si alguien
     cambia una ruta en el Kotlin, estas pruebas prueban la ruta nueva.

  2. Ejecutan contra los servicios vivos la MISMA secuencia que hace la
     aplicación, con el mismo usuario (un colaborador) y en JSON.

Lo que queda fuera: que el Kotlin compile y que la interfaz se dibuje bien.
Eso se verifica abriendo el proyecto en Android Studio, y está en el manual.
"""
import json
import os
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOVIL = os.path.join(RAIZ, "apps", "movil")
FUENTES = os.path.join(MOVIL, "app", "src", "main", "java", "mx", "com",
                       "nexum", "bienestar")

AUTH = "http://127.0.0.1:8101"
CATALOGOS = "http://127.0.0.1:8103"
PROCESO = "http://127.0.0.1:8104"
DOCUMENTOS = "http://127.0.0.1:8105"
NOTIFICACIONES = "http://127.0.0.1:8106"

COLABORADOR = "ana.perez@nexum.com.mx"
CONTRASENA = "demo123"


def kotlin(*partes):
    return open(os.path.join(FUENTES, *partes), encoding="utf-8").read()


def todo_el_kotlin():
    textos = []
    for carpeta, _, archivos in os.walk(FUENTES):
        for a in archivos:
            if a.endswith(".kt"):
                textos.append(open(os.path.join(carpeta, a), encoding="utf-8").read())
    return "\n".join(textos)


def rutas_declaradas():
    """Extrae del Kotlin las rutas /api/v1/... que la aplicación llama."""
    return sorted(set(re.findall(r'"\$url[A-Za-z]*(/api/v1/[^"?]*)', todo_el_kotlin())))


def pedir(metodo, url, token=None, cuerpo=None, tiempo=10):
    datos = None
    cabeceras = {"Accept": "application/json"}
    if cuerpo is not None:
        datos = json.dumps(cuerpo).encode("utf8")
        cabeceras["Content-Type"] = "application/json"
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"
    peticion = urllib.request.Request(url, data=datos, headers=cabeceras,
                                      method=metodo)
    try:
        with urllib.request.urlopen(peticion, timeout=tiempo) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        crudo = e.read()
        try:
            return e.code, json.loads(crudo or b"{}")
        except Exception:  # noqa: BLE001
            return e.code, {"_crudo": crudo[:200].decode("utf8", "replace")}


def _puerto(p):
    with socket.socket() as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", p)) == 0


@pytest.fixture(scope="module")
def servicios():
    necesarios = (8101, 8103, 8104, 8105, 8106)
    if not all(_puerto(p) for p in necesarios):
        guion = os.path.join(RAIZ, "scripts", "arrancar_microservicios.sh")
        if not os.path.exists(guion):
            pytest.skip("no esta el guion de arranque")
        subprocess.run(["bash", guion], capture_output=True, timeout=180, cwd=RAIZ)
        limite = time.time() + 20
        while time.time() < limite and not all(_puerto(p) for p in necesarios):
            time.sleep(1)
    if not all(_puerto(p) for p in necesarios):
        pytest.skip("los microservicios no respondieron")
    return True


@pytest.fixture
def token(servicios):
    codigo, cuerpo = pedir("POST", f"{AUTH}/api/v1/auth/login",
                           cuerpo={"correo": COLABORADOR, "contrasena": CONTRASENA})
    if codigo != 200:
        pytest.skip(f"no se pudo iniciar sesion: {cuerpo}")
    return cuerpo["token_acceso"]


# =========================================================================
# El proyecto está completo
# =========================================================================

def test_el_proyecto_android_tiene_lo_que_necesita_para_compilar():
    """Un proyecto al que le falta un archivo de Gradle no abre en el IDE."""
    obligatorios = [
        "settings.gradle.kts", "build.gradle.kts", "gradle.properties",
        "app/build.gradle.kts", "app/src/main/AndroidManifest.xml",
        "app/src/main/res/xml/rutas_archivos.xml",
        "app/src/main/res/xml/configuracion_red.xml",
    ]
    faltan = [a for a in obligatorios
              if not os.path.exists(os.path.join(MOVIL, a))]
    assert not faltan, f"Faltan archivos del proyecto: {faltan}"


def test_la_app_movil_habla_solo_json():
    """Es el requisito central de esta aplicación, el espejo del escritorio."""
    fuente = todo_el_kotlin()
    assert "application/json" in fuente
    assert "application/xml" not in fuente
    assert "formato=xml" not in fuente
    assert 'header("Accept", "application/json")' in fuente


def test_el_token_no_se_guarda_en_preferencias_normales():
    almacen = kotlin("sesion", "AlmacenSeguro.kt")
    assert "EncryptedSharedPreferences" in almacen
    assert "getSharedPreferences" not in almacen, (
        "Las preferencias normales se guardan en un XML en claro; ahí viven "
        "el token y el borrador de la encuesta.")
    manifiesto = open(os.path.join(MOVIL, "app/src/main/AndroidManifest.xml"),
                      encoding="utf-8").read()
    assert 'android:allowBackup="false"' in manifiesto, (
        "Cifrar no basta: un respaldo automático sacaría los datos del "
        "teléfono.")


def test_usa_al_menos_dos_capacidades_del_dispositivo():
    fuente = todo_el_kotlin()
    assert "EncryptedSharedPreferences" in fuente      # almacenamiento cifrado
    assert "ActivityResultContracts.TakePicture" in fuente  # cámara
    assert "ExifInterface" in fuente, (
        "La foto se sube sin sus metadatos: unas coordenadas GPS identifican "
        "a la persona sin necesidad de su nombre.")


def test_la_camara_no_pide_un_permiso_que_no_necesita():
    manifiesto = open(os.path.join(MOVIL, "app/src/main/AndroidManifest.xml"),
                      encoding="utf-8").read()
    assert "android.permission.CAMERA" not in manifiesto, (
        "Con ACTION_IMAGE_CAPTURE la foto la toma la aplicación de cámara del "
        "teléfono: pedir CAMERA sería pedir confianza que no hace falta.")
    assert 'android:required="false"' in manifiesto


def test_el_trafico_en_claro_esta_prohibido_salvo_en_desarrollo():
    config = open(os.path.join(MOVIL, "app/src/main/res/xml/configuracion_red.xml"),
                  encoding="utf-8").read()
    assert '<base-config cleartextTrafficPermitted="false"/>' in config
    assert "10.0.2.2" in config


def test_la_app_movil_consume_al_menos_cuatro_microservicios():
    fuente = todo_el_kotlin()
    usados = {s for s in ("URL_AUTH", "URL_CATALOGOS", "URL_PROCESO",
                          "URL_DOCUMENTOS", "URL_NOTIFICACIONES")
              if s in fuente}
    assert len(usados) >= 4, f"Solo consume {sorted(usados)}"


def test_atiende_un_proceso_distinto_al_de_escritorio():
    """La rúbrica pide procesos distintos, y lo son por una razón.

    La móvil responde la encuesta y levanta solicitudes; la de escritorio
    las atiende y lee el tablero. Se comprueba que no se encimen: la móvil
    NO debe llamar a los endpoints de atención ni al tablero.
    """
    movil = todo_el_kotlin()
    assert "/encuestas/respuestas" in movil
    assert "/solicitudes-apoyo" in movil
    assert "/consultas/tablero" not in movil, (
        "El tablero es de la aplicación de escritorio.")
    assert "/algoritmos/" not in movil, (
        "Las detecciones del motor de reglas son de la de escritorio.")
    assert "/estado\"" not in movil, (
        "Cambiar el estado de una solicitud es de la aplicación de escritorio: "
        "la móvil la levanta, no la atiende.")
    escritorio = open(os.path.join(RAIZ, "apps", "escritorio", "cliente.py"),
                      encoding="utf-8").read()
    assert "encuestas/respuestas" not in escritorio, (
        "Responder la encuesta es de la aplicación móvil.")


# =========================================================================
# El protocolo existe de verdad
# =========================================================================

def test_todas_las_rutas_del_kotlin_existen_en_los_servicios(token):
    """Ninguna ruta inventada: cada una responde algo que no es 404.

    Se extraen del propio código Kotlin, así que si alguien cambia una ruta
    allá, aquí se prueba la nueva.
    """
    base_por_ruta = {
        "/api/v1/auth/": AUTH,
        "/api/v1/catalogos/": CATALOGOS,
        "/api/v1/encuestas/": PROCESO,
        "/api/v1/solicitudes-apoyo": PROCESO,
        "/api/v1/documentos": DOCUMENTOS,
        "/api/v1/notificaciones/": NOTIFICACIONES,
    }
    rutas = rutas_declaradas()
    assert len(rutas) >= 8, f"Se esperaban al menos 8 rutas, se hallaron {rutas}"

    inexistentes, probadas = [], 0
    for ruta in rutas:
        base = next((v for k, v in base_por_ruta.items() if ruta.startswith(k)), None)
        assert base, f"La ruta {ruta} no corresponde a ningun servicio conocido"
        # Las rutas con partes variables se rellenan con valores reales.
        concreta = (ruta.replace("${campania.instrumentoId}", "INST-BIENESTAR")
                        .replace("${campania.versionInstrumento}", "1"))
        if "$" in concreta:
            # Una ruta armada por concatenación en varias líneas del Kotlin:
            # su parte variable no se puede resolver desde aquí. La de
            # reactivos, que es la única, se prueba completa más abajo en
            # test_el_catalogo_entrega_las_preguntas_que_la_app_dibuja.
            continue
        probadas += 1
        for metodo in ("GET", "POST"):
            codigo, _ = pedir(metodo, base + concreta, token,
                              cuerpo={} if metodo == "POST" else None)
            if codigo not in (404, 405):
                break
        else:
            inexistentes.append(ruta)
    assert not inexistentes, (
        f"Estas rutas del codigo Kotlin no existen en los servicios: "
        f"{inexistentes}")
    assert probadas >= 10, (
        f"Solo se probaron {probadas} rutas de verdad; si casi todas se "
        f"saltan, esta prueba no esta comprobando nada.")


def test_el_login_devuelve_los_campos_que_lee_el_kotlin(token):
    """Los nombres que lee SesionRepositorio tienen que ser los reales."""
    codigo, cuerpo = pedir("POST", f"{AUTH}/api/v1/auth/login",
                           cuerpo={"correo": COLABORADOR, "contrasena": CONTRASENA})
    assert codigo == 200
    fuente = kotlin("sesion", "SesionRepositorio.kt")
    for campo in re.findall(r'(?:getString|optString)\("([a-z_]+)"', fuente):
        if campo in ("token_acceso", "token_renovacion"):
            assert campo in cuerpo, f"El login no devuelve '{campo}'"
    usuario = cuerpo["usuario"]
    for campo in ("usuario_id", "nombre", "correo", "perfil", "perfil_id",
                  "unidad_alcance"):
        assert campo in usuario, f"El objeto usuario no trae '{campo}'"


def test_los_permisos_se_consultan_y_no_viajan_en_el_token(token):
    import base64
    carga = token.split(".")[1]
    carga += "=" * (-len(carga) % 4)
    reclamos = json.loads(base64.urlsafe_b64decode(carga))
    assert "permisos" not in reclamos

    codigo, cuerpo = pedir("GET", f"{AUTH}/api/v1/auth/permisos", token)
    assert codigo == 200
    assert cuerpo["perfil"] == "Colaborador"
    assert "APOYO_SOLICITAR" in cuerpo["permisos"]
    assert "AUTOREPORTE_RESPONDER" in cuerpo["permisos"]
    # Y lo que el colaborador NO puede: es lo que decide qué muestra el menú.
    assert "APOYO_ATENDER" not in cuerpo["permisos"]
    assert "AGREGADO_GLOBAL" not in cuerpo["permisos"]


def test_el_catalogo_entrega_las_preguntas_que_la_app_dibuja(token):
    """Las preguntas no están escritas en la aplicación: vienen del catálogo."""
    codigo, cuerpo = pedir("GET", f"{CATALOGOS}/api/v1/catalogos/campanias?limit=20",
                           token)
    assert codigo == 200
    campanias = cuerpo["campanias"]
    abierta = next((c for c in campanias if c["estado"] == "ABIERTA"), None)
    assert abierta, "La demostración necesita una campaña abierta"

    codigo, cuerpo = pedir(
        "GET",
        f"{CATALOGOS}/api/v1/catalogos/instrumentos/{abierta['instrumento_id']}"
        f"/versiones/{abierta['version_instrumento']}/reactivos", token)
    assert codigo == 200
    reactivos = cuerpo["reactivos"]
    assert len(reactivos) >= 5
    for campo in ("reactivo_id", "texto", "dimension_id", "orden", "invertido"):
        assert campo in reactivos[0], f"El reactivo no trae '{campo}'"


def test_el_colaborador_no_puede_entrar_donde_no_debe(token):
    """La autorización la hace el servicio, no el menú de la aplicación."""
    for base, ruta in ((PROCESO, "/api/v1/solicitudes-apoyo"),
                       (PROCESO, "/api/v1/eventos-proceso"),
                       (DOCUMENTOS, "/api/v1/documentos")):
        codigo, cuerpo = pedir("GET", base + ruta, token)
        assert codigo == 403, (
            f"{ruta} deberia negarle el acceso a un colaborador; dio {codigo}")
        assert cuerpo["error"]["codigo"] == "SIN_PERMISO"


def test_el_endpoint_de_evidencia_si_lo_puede_usar_el_colaborador(token):
    """El que la app usa para la foto: APOYO_SOLICITAR, no permisos de admin.

    Sin este endpoint, adjuntar una foto habría exigido darle al colaborador
    permisos de administración de documentos, que lo dejarían además LEER el
    repositorio entero.
    """
    codigo, cuerpo = pedir("POST", f"{DOCUMENTOS}/api/v1/documentos/evidencia-apoyo",
                           token, cuerpo={})
    assert codigo != 403, "El colaborador debe poder usar este endpoint"
    assert codigo == 422, cuerpo
    campos = {d["campo"] for d in cuerpo["error"]["detalles"]}
    assert campos == {"referencia", "contenido_base64"}


def test_la_evidencia_no_deja_que_el_cliente_elija_el_seudonimo(token):
    """Aunque el cliente lo mande, el servicio pone el suyo."""
    fuente = kotlin("datos", "EvidenciaRepositorio.kt")
    assert '"seudonimo_id"' not in fuente, (
        "La aplicación ni siquiera lo manda: lo pone el servidor.")
    servicio = open(os.path.join(RAIZ, "apps", "microservicios",
                                 "documents-service", "app.py"),
                    encoding="utf-8").read()
    bloque = servicio[servicio.index("def adjuntar_evidencia_apoyo"):]
    bloque = bloque[:bloque.index("# ------------------------------------"
                                  "-------------------------- consulta")]
    assert 'participacion["seudonimo_id"]' in bloque
    assert 'cuerpo.get("seudonimo_id")' not in bloque


def test_los_codigos_de_error_que_maneja_la_app_son_los_que_emiten_los_servicios(token):
    """Si la app espera 'SESION_REVOCADA' y el servicio dice otra cosa, el
    manejo de sesión expirada no se dispara nunca y el usuario ve un error
    que no entiende."""
    fuente = kotlin("red", "ClienteApi.kt")
    esperados = set(re.findall(r'"([A-Z_]{4,})"', fuente))

    # Token inventado -> el código que la app usa para mandar al login.
    codigo, cuerpo = pedir("GET", f"{AUTH}/api/v1/auth/validar", "no.es.un.token")
    assert codigo in (401, 403)
    real = cuerpo["error"]["codigo"]
    assert real in esperados, (
        f"El servicio responde '{real}' y la app no lo conoce. Conoce: "
        f"{sorted(c for c in esperados if c.isupper())}")

    # Almacén caído -> el código que la app usa para ofrecer reintentar.
    codigo, cuerpo = pedir("GET", f"{PROCESO}/api/v1/encuestas/respuestas/propias",
                           token)
    if codigo == 503:
        assert cuerpo["error"]["codigo"] == "ALMACEN_NO_DISPONIBLE"
        assert "ALMACEN_NO_DISPONIBLE" in esperados


def test_la_regla_d01_rechaza_un_identificador_de_empleado(token):
    """La app no manda empleado_id; si lo mandara, el servicio lo rechazaría.

    Se comprueba las dos cosas: que el código Kotlin no lo manda y que el
    servicio no lo aceptaría. La segunda es la que importa, porque la
    primera depende de que nadie la cambie.
    """
    assert "empleado_id" not in todo_el_kotlin()
    codigo, cuerpo = pedir(
        "POST", f"{PROCESO}/api/v1/encuestas/respuestas", token,
        cuerpo={"campania_id": "CAMP-2026-S5", "empleado_id": "EMP-001",
                "respuestas": [{"reactivo_id": "R-01", "valor": 3}]})
    assert codigo in (400, 422, 503), cuerpo
    if codigo != 503:
        texto = json.dumps(cuerpo).lower()
        assert "empleado" in texto or "identidad" in texto or \
               "d-01" in texto or "d01" in texto, cuerpo
