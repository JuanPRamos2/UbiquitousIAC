"""
Archivos de evidencia en documents-service.

POR QUÉ ESTAS PRUEBAS EXISTEN
-----------------------------
La validación de formato y tamaño existía y funcionaba, pero vivía dentro
del portal web. El resultado era que documents-service —cuya
responsabilidad declarada incluye «validación de formatos y tamaños» y
«protección de archivos y recuperación controlada»— solo guardaba
metadatos, y la parte difícil la hacía otro componente.

Eso tenía dos consecuencias que estas pruebas cierran:

  · la aplicación de escritorio y la móvil no podían adjuntar evidencia,
    porque hablan con los microservicios y no con el portal;
  · cualquier cliente que llamara al servicio directamente registraba un
    documento sin pasar por ninguna comprobación.

La prueba que más importa es la de la firma: es la única que distingue
«validamos el archivo» de «miramos cómo se llama».
"""
import base64
import hashlib
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVICIO = os.path.join(RAIZ, "apps", "microservicios", "documents-service")
sys.path.insert(0, SERVICIO)

import archivos  # noqa: E402
from comun import ErrorApi  # noqa: E402

PDF = b"%PDF-1.7\n% evidencia de prueba\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
EJECUTABLE = b"MZ\x90\x00" + b"\x00" * 60     # un .exe de Windows


@pytest.fixture(autouse=True)
def almacen_temporal(tmp_path, monkeypatch):
    """Cada prueba escribe en su propia carpeta."""
    monkeypatch.setenv("ALMACEN_EVIDENCIAS", str(tmp_path))
    return tmp_path


# =========================================================================
# Validación
# =========================================================================

def test_un_pdf_de_verdad_pasa():
    extension, sello, nombre = archivos.validar(PDF, "Acta de sesion.pdf")
    assert extension == "pdf"
    assert sello == hashlib.sha256(PDF).hexdigest()
    assert nombre == "Acta de sesion.pdf"


def test_un_ejecutable_renombrado_a_pdf_no_pasa():
    """La prueba que separa validar de mirar el nombre.

    Un `.exe` renombrado a `.pdf` pasa cualquier validación de extensión.
    No pasa la de firma, que es el único motivo por el que la validación
    sirve de algo.
    """
    with pytest.raises(ErrorApi) as exc:
        archivos.validar(EJECUTABLE, "inofensivo.pdf")
    assert exc.value.codigo == "ARCHIVO_INVALIDO"
    problemas = " ".join(d["problema"] for d in exc.value.detalles)
    assert "no corresponde" in problemas
    # El mensaje tiene que decir QUÉ falló: con un «archivo inválido» a
    # secas, quien lo recibe no sabe si es el formato, el tamaño o el
    # contenido.
    assert "pdf" in problemas


def test_un_formato_no_admitido_se_rechaza_nombrando_los_validos():
    with pytest.raises(ErrorApi) as exc:
        archivos.validar(PDF, "script.sh")
    problemas = " ".join(d["problema"] for d in exc.value.detalles)
    assert "no admitido" in problemas
    for formato in ("pdf", "png", "docx"):
        assert formato in problemas


def test_un_archivo_mas_grande_que_el_limite_se_rechaza():
    grande = b"%PDF-" + b"\x00" * archivos.TAMANO_MAXIMO
    with pytest.raises(ErrorApi) as exc:
        archivos.validar(grande, "enorme.pdf")
    problemas = " ".join(d["problema"] for d in exc.value.detalles)
    assert "maximo" in problemas


def test_un_archivo_vacio_se_rechaza():
    with pytest.raises(ErrorApi):
        archivos.validar(b"", "vacio.pdf")


def test_el_texto_plano_se_valida_por_decodificacion():
    """txt y csv no tienen firma: se comprueba que sean texto de verdad."""
    extension, _, _ = archivos.validar("fecha,valor\n2026-01-01,3\n".encode(),
                                       "datos.csv")
    assert extension == "csv"
    with pytest.raises(ErrorApi):
        archivos.validar(b"\xff\xfe\x00\x01binario", "mentira.txt")


# =========================================================================
# El nombre nunca se usa como ruta
# =========================================================================

@pytest.mark.parametrize("peligroso", [
    "../../etc/passwd.pdf",
    "..\\..\\windows\\system32\\x.pdf",
    "/absoluta/acta.pdf",
    "acta\x00oculto.pdf",
])
def test_un_nombre_con_ruta_no_escapa_de_la_carpeta(peligroso, almacen_temporal):
    _, sello, nombre = archivos.validar(PDF, peligroso)
    assert "/" not in nombre and "\\" not in nombre and ".." not in nombre

    archivos.guardar(PDF, sello)
    ruta = archivos.ruta_de(sello)
    # Lo que de verdad importa: el archivo quedó DENTRO del almacén.
    assert os.path.realpath(ruta).startswith(os.path.realpath(str(almacen_temporal)))
    assert os.path.exists(ruta)


# =========================================================================
# Almacenamiento y recuperación
# =========================================================================

def test_el_mismo_archivo_dos_veces_no_se_duplica():
    _, sello, _ = archivos.validar(PDF, "acta.pdf")
    assert archivos.guardar(PDF, sello) is True      # era nuevo
    assert archivos.guardar(PDF, sello) is False     # ya estaba
    assert archivos.leer(sello) == PDF


def test_dos_archivos_distintos_no_se_pisan():
    _, sello_pdf, _ = archivos.validar(PDF, "a.pdf")
    _, sello_png, _ = archivos.validar(PNG, "b.png")
    archivos.guardar(PDF, sello_pdf)
    archivos.guardar(PNG, sello_png)
    assert sello_pdf != sello_png
    assert archivos.leer(sello_pdf) == PDF
    assert archivos.leer(sello_png) == PNG


def test_un_archivo_que_no_esta_lo_dice_y_no_devuelve_vacio():
    with pytest.raises(ErrorApi) as exc:
        archivos.leer("0" * 64)
    assert exc.value.codigo == "ARCHIVO_NO_ENCONTRADO"
    assert exc.value.http == 404


def test_un_archivo_alterado_en_el_almacen_no_se_entrega():
    """El sello se recalcula al leer, y por eso esto se nota.

    Sin recalcular, una evidencia modificada después de registrarse se
    entregaría como legítima — justo lo que un sello sirve para impedir.
    """
    _, sello, _ = archivos.validar(PDF, "acta.pdf")
    archivos.guardar(PDF, sello)

    with open(archivos.ruta_de(sello), "wb") as f:
        f.write(b"%PDF-1.7\n% alterado despues de guardarse\n")

    with pytest.raises(ErrorApi) as exc:
        archivos.leer(sello)
    assert exc.value.codigo == "ARCHIVO_ALTERADO"
    assert exc.value.http == 409
    campos = {d["campo"] for d in exc.value.detalles}
    assert campos == {"sello_registrado", "sello_real"}


def test_una_escritura_a_medias_no_deja_un_archivo_valido_a_medias(almacen_temporal):
    """La escritura es a temporal y después rename, que es atómico.

    Escribir directo sobre la ruta final dejaría, si el proceso muere a la
    mitad, un archivo con el nombre correcto y el contenido truncado: el
    caso que el hash ya no detectaría, porque nadie lo vuelve a calcular.
    """
    _, sello, _ = archivos.validar(PDF, "acta.pdf")
    archivos.guardar(PDF, sello)
    carpeta = os.path.dirname(archivos.ruta_de(sello))
    assert not [f for f in os.listdir(carpeta) if f.endswith(".parcial")], (
        "Quedo un archivo .parcial: el rename no se completo.")


# =========================================================================
# El servicio lo expone de verdad
# =========================================================================

def test_documents_service_expone_la_carga_y_la_descarga():
    fuente = open(os.path.join(SERVICIO, "app.py"), encoding="utf-8").read()
    assert '/archivos"' in fuente or "/archivos'" in fuente
    assert "/archivos/<sha256>" in fuente
    assert "archivos.validar" in fuente, (
        "El endpoint tiene que validar con el modulo, no reimplementarlo.")
    assert "archivos.leer" in fuente


def test_el_portal_ya_no_valida_por_su_cuenta():
    """La validación es del servicio; el portal es un cliente más.

    Mientras el portal conserve su propia copia de las firmas, hay dos
    verdades sobre qué archivo es válido y nada obliga a que coincidan.
    """
    ruta = os.path.join(RAIZ, "apps", "web", "app", "rutas", "evidencias.py")
    if not os.path.exists(ruta):
        pytest.skip("no esta el portal en este arbol")
    fuente = open(ruta, encoding="utf-8").read()
    assert "FIRMAS = {" not in fuente, (
        "El portal mantiene su propia tabla de firmas: tiene que pedirsela "
        "a documents-service.")
