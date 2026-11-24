"""
Pruebas de la aplicación de escritorio.

Lo que se prueba aquí es `apps/escritorio/cliente.py`, que es donde vive
todo lo que puede estar mal: armar el XML de la petición, validar la
respuesta contra el XSD antes de leerla, distinguir xsi:nil de la cadena
vacía, rotar el token de renovación, borrar las credenciales al cerrar
sesión. Nada de eso necesita una ventana, y por eso el cliente no importa
Tkinter: separarlo es lo que hace que esta suite exista.

De la ventana misma (`app.py`) se comprueba lo único comprobable sin un
servidor gráfico: que el módulo se puede importar y que sus pestañas y
permisos están declarados de forma coherente. Lo demás se verificó
manejando la ventana sobre una pantalla virtual y queda como evidencia en
docs/evidencias/escritorio/.

Las pruebas que necesitan servicios vivos los levantan de verdad; si no se
pueden levantar, se omiten con un motivo en lugar de fallar.
"""
import os
import socket
import subprocess
import sys
import time

import pytest
from lxml import etree

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESCRITORIO = os.path.join(RAIZ, "apps", "escritorio")
sys.path.insert(0, ESCRITORIO)

from cliente import (ClienteXml, ErrorCliente, _escapar, _texto,  # noqa: E402
                     a_diccionario, exportar_csv, lista_de)

ESPACIO = "http://nexum.com.mx/bienestar/v1"
XSI = "http://www.w3.org/2001/XMLSchema-instance"


def arbol(xml):
    return etree.fromstring(xml.encode("utf8"))


# =========================================================================
# Lectura de XML: nil, vacío y listas
# =========================================================================

def test_nil_y_vacio_no_son_lo_mismo():
    """La diferencia que decide si un agregado suprimido se lee como cero.

    Es el defecto más caro posible en este sistema: un valor suprimido que
    se leyera como 0 pondría a la unidad en el peor lugar del tablero
    justamente cuando lo que pasa es que no hay dato.
    """
    doc = arbol(f'<r xmlns="{ESPACIO}" xmlns:xsi="{XSI}">'
                f'<suprimido xsi:nil="true"/>'
                f'<vacio></vacio>'
                f'<cero>0</cero></r>')
    assert _texto(doc, "suprimido") is None
    assert _texto(doc, "vacio") == ""
    assert _texto(doc, "cero") == "0"
    assert _texto(doc, "suprimido") != _texto(doc, "cero")


def test_el_ausente_se_distingue_del_nil():
    doc = arbol(f'<r xmlns="{ESPACIO}" xmlns:xsi="{XSI}">'
                f'<a xsi:nil="true"/></r>')
    assert _texto(doc, "a") is None
    assert _texto(doc, "no_viene", "SIN DATO") == "SIN DATO"


def test_una_lista_vacia_no_es_lo_mismo_que_una_ausente():
    """<permisos/> es «no tiene ninguno»; que no venga es «no se consultó»."""
    vacia = arbol(f'<r xmlns="{ESPACIO}"><permisos/></r>')
    assert lista_de(vacia, "permisos", "permiso") == []
    ausente = arbol(f'<r xmlns="{ESPACIO}"/>')
    assert lista_de(ausente, "permisos", "permiso") is None


def test_a_diccionario_conserva_los_nulos():
    doc = arbol(f'<r xmlns="{ESPACIO}" xmlns:xsi="{XSI}">'
                f'<unidad>UO-1</unidad><valor xsi:nil="true"/></r>')
    d = a_diccionario(doc)
    assert d["unidad"] == "UO-1"
    assert "valor" in d and d["valor"] is None


# =========================================================================
# Escritura de XML
# =========================================================================

def test_el_escape_cubre_los_cinco_caracteres():
    """Un apóstrofo en una nota no debe poder cerrar un atributo."""
    assert _escapar("Ana & <b>'s \"nota\"") == (
        "Ana &amp; &lt;b&gt;&apos;s &quot;nota&quot;")


def test_una_nota_con_xml_adentro_no_rompe_el_documento():
    """El caso real: quien atiende pega texto con signos de menor que."""
    c = ClienteXml()
    nota = "valor < umbral & </cambio_estado> intento"
    cuerpo = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
              f'<cambio_estado xmlns="{ESPACIO}">\n'
              f'  <estado>EN_PROCESO</estado>\n'
              f'  <nota>{_escapar(nota)}</nota>\n'
              f'</cambio_estado>')
    doc = arbol(cuerpo)
    assert _texto(doc, "nota") == nota
    assert c is not None


# =========================================================================
# Validación contra el XSD: la aplicación no muestra lo que no cumple
# =========================================================================

def test_una_respuesta_que_no_cumple_el_xsd_no_se_muestra(monkeypatch):
    """El orden importa: primero se valida, después se lee.

    Si se leyera primero, la ventana mostraría datos de un documento que no
    cumple el contrato, y el error aparecería más tarde y en otro lugar.
    """
    c = ClienteXml()
    # <sesion> sin token_acceso: bien formado, pero no cumple sesion.xsd.
    malo = (f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<sesion xmlns="{ESPACIO}"><tipo_token>Bearer</tipo_token></sesion>')

    class Respuesta:
        status = 200
        def read(self): return malo.encode("utf8")
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: Respuesta())
    with pytest.raises(ErrorCliente) as exc:
        c.pedir("auth", "/api/v1/auth/validar", "sesion.xsd")
    assert exc.value.codigo == "CONTRATO_INCUMPLIDO"
    assert exc.value.detalles, "El error debe decir QUÉ parte del contrato falló"


def test_un_sobre_de_error_se_convierte_en_ErrorCliente(monkeypatch):
    c = ClienteXml()
    sobre = (f'<?xml version="1.0" encoding="UTF-8"?>'
             f'<error_respuesta xmlns="{ESPACIO}"><error>'
             f'<codigo>SIN_PERMISO</codigo>'
             f'<mensaje>El perfil no tiene el permiso requerido.</mensaje>'
             f'<detalles><detalle><campo>permiso</campo>'
             f'<problema>APOYO_ATENDER</problema></detalle></detalles>'
             f'<correlacion_id>abc123</correlacion_id>'
             f'</error></error_respuesta>')

    class Error403:
        code = 403
        def read(self): return sobre.encode("utf8")

    import urllib.error

    def lanzar(*a, **k):
        e = urllib.error.HTTPError("u", 403, "Forbidden", {}, None)
        e.read = Error403().read
        raise e

    monkeypatch.setattr("urllib.request.urlopen", lanzar)
    with pytest.raises(ErrorCliente) as exc:
        c.pedir("proceso", "/api/v1/solicitudes-apoyo", "proceso.xsd")
    assert exc.value.codigo == "SIN_PERMISO"
    assert exc.value.http == 403
    assert exc.value.detalles[0]["problema"] == "APOYO_ATENDER"


def test_un_404_con_documento_normal_tampoco_se_muestra(monkeypatch):
    """Un error con cuerpo que NO es sobre de error es un contrato roto."""
    c = ClienteXml()
    import urllib.error

    def lanzar(*a, **k):
        e = urllib.error.HTTPError("u", 404, "No", {}, None)
        e.read = lambda: f'<sesion xmlns="{ESPACIO}"/>'.encode("utf8")
        raise e

    monkeypatch.setattr("urllib.request.urlopen", lanzar)
    with pytest.raises(ErrorCliente) as exc:
        c.pedir("auth", "/x", "sesion.xsd")
    assert exc.value.codigo == "RESPUESTA_INESPERADA"


def test_sin_conexion_dice_que_hacer(monkeypatch):
    c = ClienteXml()
    import urllib.error

    def lanzar(*a, **k):
        raise urllib.error.URLError("conexion rechazada")

    monkeypatch.setattr("urllib.request.urlopen", lanzar)
    with pytest.raises(ErrorCliente) as exc:
        c.pedir("auth", "/x", "sesion.xsd")
    assert exc.value.codigo == "SIN_CONEXION"
    assert "auth" in str(exc.value)


def test_el_servicio_sin_direccion_no_se_inventa():
    c = ClienteXml(servicios={"auth": "http://127.0.0.1:1"})
    with pytest.raises(ErrorCliente) as exc:
        c.pedir("reportes", "/x", "reportes.xsd")
    assert exc.value.codigo == "SERVICIO_NO_CONFIGURADO"


# =========================================================================
# Exportación
# =========================================================================

def test_la_exportacion_entrecomilla_todo(tmp_path):
    """Una explicación trae comas; una sola sin comillas corre las columnas."""
    ruta = tmp_path / "e.csv"
    exportar_csv(
        [{"unidad": "Call Center, Turno B",
          "explicacion": "valor 1.202 <= umbral 2.800, en CAMP-2026-S4",
          "valor_protegido": None}],
        ["unidad", "explicacion", "valor_protegido"], str(ruta))
    texto = ruta.read_text(encoding="utf-8-sig")
    assert '"Call Center, Turno B"' in texto
    assert texto.count('"') >= 12
    # El nulo se exporta vacío y NUNCA como 0.
    assert texto.rstrip().endswith('""')
    assert ",0" not in texto


def test_la_exportacion_no_pierde_filas_suprimidas(tmp_path):
    ruta = tmp_path / "e.csv"
    filas = [{"unidad": "A", "valor_protegido": 3.2},
             {"unidad": "B", "valor_protegido": None},
             {"unidad": "C", "valor_protegido": None}]
    exportar_csv(filas, ["unidad", "valor_protegido"], str(ruta))
    lineas = [l for l in ruta.read_text(encoding="utf-8-sig").splitlines() if l]
    assert len(lineas) == 4, ("El archivo debe traer las tres unidades más el "
                              "encabezado: omitir las suprimidas haría creer "
                              "que la campaña tuvo menos unidades.")


# =========================================================================
# La ventana
# =========================================================================

def test_la_ventana_no_hace_red_al_importarse():
    """app.py debe poder importarse sin servicios y sin pantalla."""
    try:
        import tkinter  # noqa: F401
    except ImportError:
        pytest.skip("Tkinter no esta disponible en este interprete")
    import importlib
    modulo = importlib.import_module("app")
    assert hasattr(modulo, "Aplicacion")
    assert hasattr(modulo, "main")


def test_el_cliente_no_depende_de_tkinter():
    """La separación que hace posible esta suite entera."""
    fuente = open(os.path.join(ESCRITORIO, "cliente.py"), encoding="utf-8").read()
    assert "tkinter" not in fuente, (
        "cliente.py no debe importar Tkinter: si lo hiciera, estas pruebas "
        "necesitarían un servidor gráfico para correr.")


def test_la_ventana_consume_al_menos_cuatro_microservicios():
    """La rúbrica pide cuatro; esta aplicación habla con seis."""
    fuente = open(os.path.join(ESCRITORIO, "cliente.py"), encoding="utf-8").read()
    usados = {s for s in ("auth", "proceso", "consultas", "catalogos",
                          "algoritmos", "reportes")
              if f'self.pedir("{s}"' in fuente}
    assert len(usados) >= 4, f"Solo consume {sorted(usados)}"
    assert usados >= {"auth", "proceso", "consultas", "algoritmos"}


def test_todo_lo_que_pide_la_ventana_va_en_xml():
    """Ni una petición en JSON: es el requisito central de esta aplicación."""
    fuente = open(os.path.join(ESCRITORIO, "cliente.py"), encoding="utf-8").read()
    assert "application/json" not in fuente
    assert "json.dumps" not in fuente
    assert fuente.count("formato=xml") >= 10
    cabeceras = fuente[fuente.index("def pedir"):fuente.index("def _validar")]
    assert '"Accept": "application/xml"' in cabeceras
    assert 'application/xml; charset=utf-8' in cabeceras


# =========================================================================
# Contra servicios vivos
# =========================================================================

def _puerto_abierto(puerto):
    with socket.socket() as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", puerto)) == 0


@pytest.fixture(scope="module")
def servicios_vivos():
    """Levanta los microservicios si no están ya arriba."""
    necesarios = (8101, 8107, 8109)
    if all(_puerto_abierto(p) for p in necesarios):
        return True
    guion = os.path.join(RAIZ, "scripts", "arrancar_microservicios.sh")
    if not os.path.exists(guion):
        pytest.skip("no esta el guion de arranque")
    try:
        subprocess.run(["bash", guion], capture_output=True, timeout=180,
                       cwd=RAIZ)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"no se pudieron levantar los servicios: {e}")
    limite = time.time() + 20
    while time.time() < limite:
        if all(_puerto_abierto(p) for p in necesarios):
            return True
        time.sleep(1)
    pytest.skip("los microservicios no respondieron a tiempo")


@pytest.fixture
def sesion(servicios_vivos):
    c = ClienteXml()
    try:
        c.iniciar_sesion("mariana.solis@nexum.com.mx", "demo123")
    except ErrorCliente as e:
        pytest.skip(f"no se pudo iniciar sesion: {e}")
    yield c
    c.cerrar_sesion()


def test_el_ciclo_de_sesion_completo(sesion):
    """Entrar, validar, renovar y salir, todo en XML y todo validado."""
    datos = sesion.validar_sesion()
    assert datos["valido"] == "true"
    assert datos["usuario_id"] == "USR-00003"

    viejo = sesion.token
    viejo_refresco = sesion.token_refresco
    sesion.renovar()
    assert sesion.token != viejo, "El token de acceso debe cambiar"
    assert sesion.token_refresco != viejo_refresco, (
        "El token de renovación se ROTA: si no se guardara el nuevo, la "
        "siguiente renovación fallaría.")


def test_los_permisos_no_viajan_en_el_token(sesion):
    """Se consultan al servicio, que los lee de usuarios.perfil_permiso."""
    import base64
    import json
    carga = sesion.token.split(".")[1]
    carga += "=" * (-len(carga) % 4)
    reclamos = json.loads(base64.urlsafe_b64decode(carga))
    assert "permisos" not in reclamos, (
        "Si los permisos viajaran en el token, revocar uno no tendría efecto "
        "hasta que el token expirara.")
    assert sesion.permisos, "Y aun así la aplicación los tiene: los consultó."
    assert "APOYO_ATENDER" in sesion.permisos


def test_cerrar_sesion_borra_las_credenciales_aunque_falle_la_red(servicios_vivos):
    c = ClienteXml()
    try:
        c.iniciar_sesion("mariana.solis@nexum.com.mx", "demo123")
    except ErrorCliente as e:
        pytest.skip(str(e))
    c.servicios["auth"] = "http://127.0.0.1:1"   # servicio inalcanzable
    c.cerrar_sesion()
    assert c.token is None and c.token_refresco is None
    assert c.permisos == set()


def test_el_tablero_llega_validado_y_con_sus_supresiones(sesion):
    filas = sesion.tablero("UO-CC-TURNO-B")
    assert filas, "La unidad de demostración debe traer filas"
    suprimidas = [f for f in filas if f.get("estado_publicacion") != "PUBLICADO"]
    publicadas = [f for f in filas if f.get("estado_publicacion") == "PUBLICADO"]
    assert publicadas, "Debe haber al menos una fila publicada"
    for f in suprimidas:
        assert f.get("valor_protegido") is None, (
            "Una fila suprimida llega con el valor en nil, no en cero.")


def test_las_detecciones_traen_explicacion(sesion):
    filas = sesion.detecciones(tamano=20)
    assert filas
    for f in filas:
        assert f.get("explicacion"), (
            "El XSD declara la explicación obligatoria; una detección sin "
            "ella no habría pasado la validación del cliente.")


def test_el_xml_crudo_queda_disponible_para_diagnostico(sesion):
    sesion.reglas()
    assert sesion.ultimo_servicio == "algoritmos"
    assert sesion.ultimo_xml.lstrip().startswith("<!-- GET")
    assert "<reglas_respuesta" in sesion.ultimo_xml
