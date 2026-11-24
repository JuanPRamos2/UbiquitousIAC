"""
PDF, Excel, reportes comparativos y Highcharts en reports-service.

La especificación del servicio exige las cuatro cosas y no existía ninguna:
el servicio entregaba solo JSON, CSV y XML.

LO QUE DE VERDAD SE PRUEBA AQUÍ
-------------------------------
No que el archivo «se genere» —eso lo diría cualquier prueba que mire el
código de respuesta—, sino que los formatos nuevos CONSERVEN las dos
reglas que hacen defendibles a los viejos:

  · las filas suprimidas se exportan, con su motivo y sin valor;
  · un nulo no se convierte en cero por el camino.

La segunda es el error más caro posible en este sistema. Una celda vacía
en Excel se suma como cero, y un promedio con ceros de unidades suprimidas
da un número más bajo, que aquí significa «peor bienestar».
"""
import io
import os

import pytest

# El módulo vive en la capa común porque lo usan dos servicios:
# reports-service exporta un reporte propio y export-service exporta una
# selección libre de agregados. Las reglas que estas pruebas comprueban
# —la fila suprimida se exporta, el nulo es «—» y nunca cero— tienen que
# valer igual en los dos, y con una copia por servicio no valdrían.
from comun import formatos

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DOC = {
    "reporte_id": "RPT-PRUEBA00001",
    "tipo": "TABLERO_CAMPANIA",
    "titulo": "Resultados protegidos por unidad y dimension",
    "fecha_generacion": "2026-11-04T10:00:00+00:00",
    "perfil_generador": "Especialista de bienestar",
    "sello_sha256": "a" * 64,
    "total_filas": 3,
    "filas_suprimidas": 1,
    "epsilon_consumido": 0.0,
}
COLUMNAS = ["unidad", "dimension", "estado_publicacion", "valor_protegido",
            "escala_ruido"]
FILAS = [
    {"unidad": "Call Center - Turno B", "dimension": "Carga percibida",
     "estado_publicacion": "PUBLICADO", "valor_protegido": 1.202,
     "escala_ruido": 0.35},
    {"unidad": "Logistica - Turno A", "dimension": "Carga percibida",
     "estado_publicacion": "GRUPO_INSUFICIENTE", "valor_protegido": None,
     "escala_ruido": None},
    {"unidad": "Calidad - Turno 1", "dimension": "Carga percibida",
     "estado_publicacion": "PUBLICADO", "valor_protegido": 3.887,
     "escala_ruido": 0.35},
]


# =========================================================================
# Excel
# =========================================================================

def test_el_excel_se_abre_y_trae_todas_las_filas():
    from openpyxl import load_workbook
    hoja = load_workbook(io.BytesIO(formatos.a_excel(DOC, FILAS, COLUMNAS))).active
    textos = [str(c.value) for fila in hoja.iter_rows() for c in fila
              if c.value is not None]
    for unidad in ("Call Center - Turno B", "Logistica - Turno A",
                   "Calidad - Turno 1"):
        assert unidad in textos, (
            f"Falta {unidad}. Omitir una fila suprimida haria creer que la "
            f"campana tuvo menos unidades de las que tuvo.")


def test_un_valor_suprimido_no_se_escribe_como_cero_en_excel():
    """El error más caro: una celda vacía se suma como cero.

    Se escribe el texto «—» y no una celda numérica vacía, justamente para
    que no entre en una fórmula sin que nadie se dé cuenta.
    """
    from openpyxl import load_workbook
    hoja = load_workbook(io.BytesIO(formatos.a_excel(DOC, FILAS, COLUMNAS))).active

    columna = COLUMNAS.index("valor_protegido") + 1
    valores = [hoja.cell(row=f, column=columna).value
               for f in range(8, 8 + len(FILAS))]
    assert "—" in valores, f"El nulo no quedo como guion: {valores}"
    assert 0 not in valores and "0" not in valores, (
        f"Un valor suprimido se escribio como cero: {valores}")


def test_el_excel_dice_por_escrito_que_los_valores_traen_ruido():
    """Quien recibe el archivo suelto no tiene el contexto de la pantalla."""
    from openpyxl import load_workbook
    hoja = load_workbook(io.BytesIO(formatos.a_excel(DOC, FILAS, COLUMNAS))).active
    todo = " ".join(str(c.value) for fila in hoja.iter_rows() for c in fila
                    if c.value)
    assert "ruido" in todo.lower()
    assert "suprimid" in todo.lower()
    assert DOC["sello_sha256"] in todo


# =========================================================================
# PDF
# =========================================================================

def test_el_pdf_es_un_pdf_de_verdad():
    datos = formatos.a_pdf(DOC, FILAS, COLUMNAS)
    assert datos.startswith(b"%PDF-"), "No tiene la firma de un PDF"
    assert b"%%EOF" in datos[-2048:], "No esta cerrado"
    assert len(datos) > 1500


def test_el_pdf_incluye_las_unidades_y_el_sello():
    """Se extrae el texto de verdad en lugar de buscar bytes crudos.

    En un PDF el texto va comprimido, así que buscar la cadena en los
    bytes del archivo no probaría nada: pasaría o fallaría por razones que
    no tienen que ver con el contenido.
    """
    pdfminer = pytest.importorskip("pdfminer.high_level",
                                   reason="pdfminer no esta instalado")
    texto = pdfminer.extract_text(io.BytesIO(formatos.a_pdf(DOC, FILAS, COLUMNAS)))
    for unidad in ("Call Center", "Logistica", "Calidad"):
        assert unidad in texto
    assert DOC["sello_sha256"][:16] in texto
    assert "ruido" in texto.lower()
    # La fila suprimida sale con guion, no con cero.
    assert "—" in texto


def test_el_pdf_sin_filas_no_truena():
    datos = formatos.a_pdf({**DOC, "total_filas": 0, "filas_suprimidas": 0},
                           [], COLUMNAS)
    assert datos.startswith(b"%PDF-")


# =========================================================================
# Highcharts
# =========================================================================

def test_la_grafica_no_mete_las_suprimidas_como_ceros():
    """Meterlas como ceros haría ver un problema donde no hay dato."""
    salida = formatos.a_highcharts(DOC, FILAS, COLUMNAS)
    assert salida["graficable"] is True
    datos = salida["configuracion"]["series"][0]["data"]
    assert len(datos) == 2, f"Se graficaron {len(datos)} de 2 publicadas"
    assert 0 not in datos
    assert salida["filas_suprimidas"] == 1
    # Y el subtítulo lo dice: si no, la gráfica miente por omisión.
    subtitulo = salida["configuracion"]["subtitle"]["text"]
    assert "suprimid" in subtitulo.lower()
    assert "ruido" in subtitulo.lower()


def test_un_reporte_sin_columna_numerica_dice_por_que_no_se_grafica():
    """Forzar una gráfica produciría una que no dice nada."""
    salida = formatos.a_highcharts(
        {"titulo": "Bitacora"}, [{"accion": "X", "resultado": "EXITO"}],
        ["accion", "resultado"])
    assert salida["graficable"] is False
    assert "motivo" in salida and salida["motivo"]


# =========================================================================
# El servicio los expone
# =========================================================================

def test_el_servicio_declara_los_cinco_formatos():
    fuente = open(os.path.join(RAIZ, "apps", "microservicios", "reports-service",
                               "app.py"), encoding="utf-8").read()
    for formato in ("json", "csv", "xml", "xlsx", "pdf"):
        assert f'"{formato}"' in fuente
    assert "/comparativo" in fuente
    assert "/grafica" in fuente
