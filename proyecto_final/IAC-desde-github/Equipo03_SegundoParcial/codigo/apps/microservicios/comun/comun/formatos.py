"""
Generación de los formatos de salida: PDF y Excel.

POR QUÉ VIVE EN LA CAPA COMÚN Y NO EN UN SERVICIO
--------------------------------------------------
Lo usan dos servicios: reports-service, que exporta un reporte que él
mismo generó, y export-service, que exporta una selección libre de
agregados. Las reglas de abajo —las filas suprimidas se exportan, el nulo
se escribe «—» y nunca cero, el archivo dice por escrito que el valor
lleva ruido— tienen que valer igual en los dos. Con una copia por
servicio, arreglar una y olvidar la otra produce dos archivos del mismo
dato que no dicen lo mismo, y es justo la clase de inconsistencia que no
se nota hasta que alguien compara.

`openpyxl` y `reportlab` se importan DENTRO de cada función, no aquí
arriba. Así este módulo puede estar en la capa común sin que los once
servicios tengan que instalar dos librerías que solo dos usan: están
declaradas únicamente en los requirements de reports-service y
export-service.

POR QUÉ ESTE MÓDULO
-------------------
La especificación del servicio exige exportación en PDF y Excel, además de
CSV y XML. El servicio entregaba solo los tres de texto. CSV se abre en
Excel, pero no es un archivo de Excel: no lleva tipos, ni anchos, ni
formato, y quien lo recibe tiene que arreglarlo a mano cada vez.

LO QUE LOS DOS FORMATOS TIENEN QUE CONSERVAR
--------------------------------------------
Las dos reglas que el servicio ya aplicaba a los formatos de texto valen
igual aquí, y son las que hacen que estos archivos sean defendibles:

1. **Las filas suprimidas SE EXPORTAN**, con su motivo y sin valor. Un PDF
   que las omitiera haría creer que la campaña tuvo menos unidades de las
   que tuvo: se leerían 8 de 8 unidades publicadas cuando en realidad
   fueron 8 de 12.

2. **El valor publicado trae ruido.** No es el promedio real de la unidad.
   Los dos formatos lo dicen por escrito, en el documento, no en una nota
   al pie que se pierde al imprimir: quien reciba el archivo suelto, sin
   el contexto de la pantalla, tiene que poder saberlo.

3. **Todo sale del documento YA GUARDADO**, nunca de una consulta nueva.
   Si se volviera a consultar la base, el PDF y el CSV del mismo reporte
   podrían diferir y el sello no cuadraría con ninguno de los dos.

POR QUÉ UN NULO SE ESCRIBE COMO «—» Y NO COMO CERO
---------------------------------------------------
Es el error más caro posible en este sistema. Una celda vacía en Excel se
suma como cero, y un promedio que incluya ceros de unidades suprimidas da
un número más bajo que el real, que en esta plataforma significa «peor
bienestar». En el Excel se escribe el texto «—» y no una celda vacía
numérica, justamente para que no entre en una fórmula sin que nadie se dé
cuenta.
"""
import datetime as dt
import io

NOTA_RUIDO = (
    "Los valores publicados llevan ruido de Laplace (privacidad "
    "diferencial): no son el promedio real de la unidad y no deben "
    "tratarse como tal. Las filas sin valor fueron suprimidas por no "
    "alcanzar el umbral minimo de grupo; se incluyen a proposito, porque "
    "omitirlas haria creer que la campana tuvo menos unidades de las que "
    "tuvo."
)


def _texto(valor):
    """Un nulo es «—», nunca vacío ni cero. Ver el encabezado del módulo."""
    if valor is None:
        return "—"
    if isinstance(valor, bool):
        return "si" if valor else "no"
    return str(valor)


# =========================================================================
# Excel
# =========================================================================

def a_excel(doc, filas, columnas):
    """Devuelve los bytes de un .xlsx.

    Se usa openpyxl y no una escritura manual de XML porque el formato de
    Excel moderno es un ZIP con varias partes relacionadas; escribirlo a
    mano produce archivos que Excel abre «reparando», y un archivo que el
    programa dice reparar no es algo que se le entregue a nadie.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Reporte"

    # --- Encabezado del documento, antes de la tabla -------------------
    hoja["A1"] = doc.get("titulo") or doc.get("tipo", "Reporte")
    hoja["A1"].font = Font(bold=True, size=14)
    hoja["A2"] = (f"Reporte {doc.get('reporte_id')} · generado "
                  f"{(doc.get('fecha_generacion') or '')[:16]}")
    hoja["A3"] = (f"Filas: {doc.get('total_filas', len(filas))} · "
                  f"suprimidas: {doc.get('filas_suprimidas', 0)} · "
                  f"epsilon consumido: {doc.get('epsilon_consumido', 0)}")
    hoja["A4"] = f"Sello SHA-256: {doc.get('sello_sha256', '')}"
    hoja["A5"] = NOTA_RUIDO
    hoja["A5"].alignment = Alignment(wrap_text=True, vertical="top")
    hoja.merge_cells(start_row=5, start_column=1, end_row=5,
                     end_column=max(len(columnas), 1))
    hoja.row_dimensions[5].height = 46

    # --- Tabla ----------------------------------------------------------
    fila_encabezado = 7
    relleno = PatternFill("solid", fgColor="1F3864")
    for j, columna in enumerate(columnas, start=1):
        celda = hoja.cell(row=fila_encabezado, column=j,
                          value=columna.replace("_", " "))
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = relleno

    for i, fila in enumerate(filas, start=fila_encabezado + 1):
        for j, columna in enumerate(columnas, start=1):
            valor = fila.get(columna)
            if valor is None:
                # Texto, no celda vacía: una celda vacía se suma como cero.
                hoja.cell(row=i, column=j, value="—")
            elif isinstance(valor, (int, float)) and not isinstance(valor, bool):
                hoja.cell(row=i, column=j, value=valor)
            else:
                hoja.cell(row=i, column=j, value=_texto(valor))

    # Ancho por el contenido real, con tope: una explicación de 300
    # caracteres haría una columna que no cabe en ninguna pantalla.
    for j, columna in enumerate(columnas, start=1):
        ancho = max([len(str(columna))] +
                    [len(_texto(f.get(columna))) for f in filas[:200]] or [10])
        hoja.column_dimensions[get_column_letter(j)].width = min(max(ancho + 2, 10), 60)

    hoja.freeze_panes = hoja.cell(row=fila_encabezado + 1, column=1)

    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


# =========================================================================
# PDF
# =========================================================================

def a_pdf(doc, filas, columnas):
    """Devuelve los bytes de un PDF apaisado con la tabla paginada.

    Apaisado porque estos reportes tienen entre siete y once columnas, y
    en vertical quedarían ilegibles. La tabla se parte en páginas con el
    encabezado repetido: una tabla de 200 filas sin encabezado repetido
    obliga a volver a la primera página para saber qué columna se está
    leyendo.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate,
                                    Spacer, Table, TableStyle)

    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
        title=doc.get("titulo") or "Reporte", author="Bienestar Nexum")

    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle("titulo", parent=estilos["Heading1"],
                            fontSize=15, textColor=colors.HexColor("#1F3864"),
                            spaceAfter=4)
    tenue = ParagraphStyle("tenue", parent=estilos["Normal"],
                           fontSize=8, textColor=colors.HexColor("#555555"),
                           leading=11)
    celda = ParagraphStyle("celda", parent=estilos["Normal"], fontSize=7,
                           leading=8.5)
    celda_encabezado = ParagraphStyle("ce", parent=celda, fontSize=7.5,
                                      textColor=colors.white)

    piezas = [
        Paragraph(doc.get("titulo") or doc.get("tipo", "Reporte"), titulo),
        Paragraph(f"Reporte {doc.get('reporte_id')} · generado "
                  f"{(doc.get('fecha_generacion') or '')[:16]} · "
                  f"perfil {doc.get('perfil_generador', '')}", tenue),
        Paragraph(f"Filas: {doc.get('total_filas', len(filas))} · "
                  f"suprimidas: {doc.get('filas_suprimidas', 0)} · "
                  f"épsilon consumido: {doc.get('epsilon_consumido', 0)}", tenue),
        Paragraph(f"Sello SHA-256: {doc.get('sello_sha256', '')}", tenue),
        Spacer(1, 4 * mm),
        Paragraph(NOTA_RUIDO, tenue),
        Spacer(1, 4 * mm),
    ]

    encabezado = [Paragraph(c.replace("_", " "), celda_encabezado)
                  for c in columnas]

    # Se parte en bloques para que ninguna tabla crezca sin control: una
    # sola tabla de miles de filas hace que reportlab calcule el diseño
    # entero en memoria antes de escribir la primera página.
    POR_PAGINA = 24
    estilo_tabla = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3864")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#BBBBBB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#F4F6F8")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ])

    if not filas:
        piezas.append(Paragraph("El reporte no devolvió filas.", tenue))
    else:
        for inicio in range(0, len(filas), POR_PAGINA):
            bloque = filas[inicio:inicio + POR_PAGINA]
            datos = [encabezado]
            for fila in bloque:
                datos.append([Paragraph(_texto(fila.get(c)), celda)
                              for c in columnas])
            tabla = Table(datos, repeatRows=1, hAlign="LEFT")
            tabla.setStyle(estilo_tabla)
            piezas.append(tabla)
            if inicio + POR_PAGINA < len(filas):
                piezas.append(PageBreak())

    def pie(canvas, documento):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawString(12 * mm, 8 * mm,
                          f"Bienestar Nexum · {doc.get('reporte_id', '')}")
        canvas.drawRightString(landscape(A4)[0] - 12 * mm, 8 * mm,
                               f"Página {documento.page}")
        canvas.restoreState()

    pdf.build(piezas, onFirstPage=pie, onLaterPages=pie)
    return buffer.getvalue()


# =========================================================================
# Highcharts
# =========================================================================

def a_highcharts(doc, filas, columnas):
    """Arma la configuración de Highcharts para este reporte.

    Devuelve la CONFIGURACIÓN, no una imagen. El servicio no dibuja: el
    portal ya sirve Highcharts localmente y es quien tiene la pantalla. Un
    microservicio que generara imágenes necesitaría un navegador sin
    interfaz dentro del contenedor —decenas de megabytes y una superficie
    de ataque nueva— para producir algo que el navegador del usuario dibuja
    gratis.

    La serie se arma solo con las filas PUBLICADAS, y el conteo de
    suprimidas viaja aparte, en el subtítulo. Meterlas como ceros movería
    la gráfica hacia abajo y haría ver un problema donde lo que hay es
    ausencia de dato.
    """
    serie_columna = next(
        (c for c in ("valor_protegido", "cobertura_porcentaje", "total",
                     "n_observaciones") if c in columnas), None)
    etiqueta_columna = next(
        (c for c in ("unidad", "dimension", "campania_id",
                     "unidad_organizacional_id") if c in columnas), None)

    if not serie_columna or not etiqueta_columna:
        # No todo reporte es graficable, y forzarlo produciría una gráfica
        # que no dice nada. Se dice por qué, en lugar de devolver vacío.
        return {"graficable": False,
                "motivo": "Este reporte no tiene una columna numérica y una "
                          "de agrupación que permitan una serie con sentido."}

    publicadas = [f for f in filas if f.get(serie_columna) is not None]
    suprimidas = len(filas) - len(publicadas)

    return {
        "graficable": True,
        "configuracion": {
            "chart": {"type": "column"},
            "title": {"text": doc.get("titulo") or doc.get("tipo")},
            "subtitle": {
                "text": (f"{len(publicadas)} con valor publicado · "
                         f"{suprimidas} suprimidas (no se grafican: no son "
                         f"cero, no hay dato) · valores con ruido de Laplace")},
            "xAxis": {"categories": [_texto(f.get(etiqueta_columna))
                                     for f in publicadas],
                      "labels": {"rotation": -45}},
            "yAxis": {"title": {"text": serie_columna.replace("_", " ")}},
            "legend": {"enabled": False},
            "credits": {"enabled": False},
            "series": [{
                "name": serie_columna.replace("_", " "),
                "data": [float(f.get(serie_columna)) for f in publicadas],
            }],
        },
        "columna_valor": serie_columna,
        "columna_etiqueta": etiqueta_columna,
        "filas_suprimidas": suprimidas,
    }


def ahora_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat()
