"""
Los documentos no pueden contradecir al repositorio.

POR QUÉ EXISTE ESTE ARCHIVO
---------------------------
La entrega anterior se fue con los documentos diciendo «nueve
microservicios» cuando ya había más, «las seis migraciones» cuando ya
había diez, y un conteo de pruebas viejo. Ninguna de esas cifras rompía
nada, y ahí está el problema: una cifra desfasada no falla, solo hace
dudar de todo lo demás del documento. Fue parte de la retroalimentación
que recibió el equipo.

Un documento es la única parte del proyecto que no se ejecuta, así que es
la única que puede quedarse mintiendo sin que nada avise. Esto es lo que
avisa.

Lo que NO comprueba: la prosa. No hay forma de verificar
automáticamente si una explicación es buena. Lo que sí se puede verificar
es que los números y los nombres coincidan con lo que hay, y resulta que
eso es justo lo que se desfasa.
"""
import os
import re

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(RAIZ, "docs")

docx = pytest.importorskip("docx", reason="python-docx no esta instalado")

DOCUMENTOS = sorted(f for f in os.listdir(DOCS) if f.endswith(".docx")) \
    if os.path.isdir(DOCS) else []

NUMEROS = {6: "seis", 7: "siete", 8: "ocho", 9: "nueve", 10: "diez",
           11: "once", 12: "doce", 13: "trece", 14: "catorce",
           15: "quince", 16: "dieciséis", 17: "diecisiete",
           18: "dieciocho", 19: "diecinueve", 20: "veinte",
           21: "veintiuno", 22: "veintidós", 23: "veintitrés",
           24: "veinticuatro", 25: "veinticinco", 26: "veintiséis",
           27: "veintisiete", 28: "veintiocho", 29: "veintinueve",
           30: "treinta"}


def _texto(nombre):
    """Todo el texto del documento: párrafos y celdas de tabla.

    Las tablas se incluyen porque es donde viven los puertos y los nombres
    de servicio, que es justo lo que se desfasa.
    """
    d = docx.Document(os.path.join(DOCS, nombre))
    partes = [p.text for p in d.paragraphs]
    for t in d.tables:
        for fila in t.rows:
            partes.extend(c.text for c in fila.cells)
    return "\n".join(partes)


@pytest.fixture(scope="module")
def servicios():
    base = os.path.join(RAIZ, "apps", "microservicios")
    return sorted(n for n in os.listdir(base)
                  if os.path.isdir(os.path.join(base, n))
                  and n not in ("comun", "comun-node"))


@pytest.fixture(scope="module")
def puertos():
    import yaml
    compose = yaml.safe_load(
        open(os.path.join(RAIZ, "docker-compose.yml"), encoding="utf-8"))
    salida = {}
    for nombre, definicion in (compose.get("services") or {}).items():
        for puerto in (definicion or {}).get("ports") or []:
            salida[nombre] = str(puerto).split(":")[0]
    return salida


@pytest.mark.skipif(not DOCUMENTOS, reason="no hay documentos")
@pytest.mark.parametrize("documento", DOCUMENTOS)
def test_ningun_documento_afirma_un_conteo_de_servicios_viejo(documento,
                                                              servicios,
                                                              puertos):
    """«nueve microservicios» con dieciséis en el árbol es una mentira.

    QUÉ CUENTA COMO CORRECTO, Y POR QUÉ NO ES UN SOLO NÚMERO
    --------------------------------------------------------
    En estos documentos conviven varios conteos, y todos son ciertos a la
    vez:

      · dieciséis microservicios;
      · catorce en Python y dos en Node;
      · veinte servicios en el compose, que suma PostgreSQL, MongoDB,
        Redis y el portal.

    La primera versión de esta prueba exigía un único número y marcaba
    como error «catorce servicios están en Python» y «levanta veinte
    servicios», que son correctas. Una prueba que empuja a «corregir»
    algo cierto es peor que no tener prueba, así que los conteos
    admisibles se derivan del repositorio: si alguien agrega un servicio,
    el conjunto cambia solo.
    """
    texto = _texto(documento)
    n_micro = len(servicios)
    n_node = sum(1 for s in servicios
                 if os.path.exists(os.path.join(
                     RAIZ, "apps", "microservicios", s, "package.json")))
    admisibles = {n_micro, n_micro - n_node, n_node, len(puertos)}

    malas = []
    for n, palabra in NUMEROS.items():
        if n in admisibles:
            continue
        for sustantivo in ("microservicios", "servicios"):
            if re.search(rf"\b{palabra} {sustantivo}\b", texto, re.I):
                malas.append(f"«{palabra} {sustantivo}»")

    assert not malas, (
        f"{documento} afirma {', '.join(sorted(set(malas)))}, y los unicos "
        f"conteos ciertos son {sorted(admisibles)}: {n_micro} "
        f"microservicios ({NUMEROS[n_micro]}), {n_micro - n_node} en "
        f"Python, {n_node} en Node y {len(puertos)} en el compose. "
        f"Regenera con `python3 docs/actualizar_documentos.py`.")

@pytest.mark.skipif(not DOCUMENTOS, reason="no hay documentos")
@pytest.mark.parametrize("documento", DOCUMENTOS)
def test_ningun_documento_afirma_un_conteo_de_garantias_viejo(documento):
    """Las garantías se cuentan del SQL, que es donde se declaran."""
    declaradas = set()
    for carpeta in (os.path.join(RAIZ, "db", "esquema"),
                    os.path.join(RAIZ, "db", "migraciones")):
        for archivo in sorted(os.listdir(carpeta)):
            if archivo.endswith(".sql"):
                declaradas |= set(re.findall(
                    r"'(G\d) ",
                    open(os.path.join(carpeta, archivo),
                         encoding="utf-8").read()))
    texto = _texto(documento)
    correcto = NUMEROS[len(declaradas)]
    malas = [p for n, p in NUMEROS.items()
             if n != len(declaradas)
             and re.search(rf"\b{p} garant[ií]as\b", texto, re.I)]
    assert not malas, (
        f"{documento} afirma «{malas[0]} garantías» y hay "
        f"{len(declaradas)} ({correcto}): {sorted(declaradas)}.")


@pytest.mark.skipif(not DOCUMENTOS, reason="no hay documentos")
@pytest.mark.parametrize("documento", DOCUMENTOS)
def test_ningun_documento_afirma_un_conteo_de_migraciones_viejo(documento):
    carpeta = os.path.join(RAIZ, "db", "migraciones")
    cuantas = len([f for f in os.listdir(carpeta) if f.endswith(".sql")])
    texto = _texto(documento)
    malas = [p for n, p in NUMEROS.items()
             if n != cuantas
             and re.search(rf"\b{p} migraciones\b", texto, re.I)]
    assert not malas, (
        f"{documento} afirma «{malas[0]} migraciones» y hay {cuantas}.")


def test_el_manual_documenta_el_puerto_real_de_cada_servicio(servicios,
                                                             puertos):
    """Un puerto equivocado en el manual es media hora perdida.

    Y es el error más fácil de cometer: el puerto que el manual documenta
    es el PUBLICADO, el que alguien escribe en el navegador, mientras que
    dentro de la red interna los dieciséis escuchan en 8000. Las dos
    cifras conviven en el repositorio.
    """
    manual = "Manual_Tecnico_y_Demostracion_Equipo03.docx"
    if manual not in DOCUMENTOS:
        pytest.skip("no esta el manual")
    texto = _texto(manual)
    problemas = []
    for servicio in servicios:
        if servicio not in texto:
            problemas.append(f"{servicio} no aparece en el manual")
            continue
        esperado = puertos.get(servicio)
        if esperado and esperado not in texto:
            problemas.append(f"{servicio} deberia figurar con el puerto "
                             f"{esperado}")
    assert not problemas, (
        f"El manual no coincide con el compose: {problemas}. Alguien que "
        f"siga el manual escribe un puerto que no responde.")


def test_los_documentos_nombran_a_los_dos_responsables_reales(servicios):
    """La retroalimentación pedía que cada integrante dueñe sus servicios.

    Donde el documento decía «Consultas» o «Reportes» sin nombre, ahora
    tiene que haber un nombre: es lo que se pidió explícitamente.
    """
    faltan = []
    for documento in ("Modulo_Microservicios_Completo_Equipo03.docx",
                      "Reporte_Tecnico_Integrado_Equipo03.docx",
                      "Manual_Tecnico_y_Demostracion_Equipo03.docx"):
        if documento not in DOCUMENTOS:
            continue
        texto = _texto(documento)
        for nombre in ("Emiliano", "Gerardo"):
            if nombre not in texto:
                faltan.append(f"{documento} no menciona a {nombre}")
    assert not faltan, faltan


def test_los_servicios_nuevos_estan_documentados(servicios):
    """Un servicio que no está en ningún documento es un servicio que
    nadie puede defender porque nadie sabe que existe."""
    nuevos = ("trends-service", "interventions-service", "export-service",
              "sync-service", "configuration-service", "monitoring-service",
              "integration-service",
              "consent-service", "privacy-service", "survey-service",
              "indicators-service", "support-service",
              "organizational-service", "audit-service",
              "data-governance-service")
    todo = "\n".join(_texto(d) for d in DOCUMENTOS)
    faltan = [s for s in nuevos if s in servicios and s not in todo]
    assert not faltan, (
        f"Estos servicios existen y ningun documento los nombra: {faltan}.")
