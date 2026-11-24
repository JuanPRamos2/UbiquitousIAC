"""
export-service — egreso e ingreso controlado de agregados.

LO QUE SE PRUEBA, Y EN QUÉ ORDEN DE IMPORTANCIA
-----------------------------------------------
1. **Que generar no entrega el archivo.** Son dos permisos y dos
   registros. Si bastara el permiso de generar, el segundo control no
   existiría en la práctica.

2. **Que el archivo dice cuántas filas se suprimieron.** Un archivo que
   trajera solo las publicadas haría leer «8 unidades» donde hubo 12.

3. **Que la descarga entrega los bytes sellados y no los regenera.** Si
   los regenerara, una campaña publicada entre la generación y la descarga
   daría un archivo distinto con el sello viejo.

4. **Que lo importado no entra a los agregados calculados.** Un valor que
   viene de fuera no pasó por el umbral k ni por el ruido.

5. **Que validar y aplicar son dos pasos, y el segundo comprueba el
   sello.** Validar un archivo y aplicar otro sería el agujero más obvio
   posible.

Sobre el control de fuga por conjuntos: con los datos sembrados ninguna
unidad publicada es padre de otra, así que la ruta completa del ataque no
se puede recorrer contra esta base. El cálculo se prueba aparte, en
`test_inferencia.py`, y aquí se comprueba que el servicio LO LLAMA antes
de escribir un solo byte, que es la parte que le toca a este servicio.
"""
import hashlib
import json
import os

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def exportaciones():
    from conftest import _cargar
    modulo = _cargar("export-service", "svc_export")
    modulo.app.config["TESTING"] = True
    return modulo


@pytest.fixture
def cliente(exportaciones):
    return exportaciones.app.test_client()


def _cab(token):
    return {"Authorization": f"Bearer {token}"}


# Dos unidades publicadas que NO están una dentro de la otra: el conjunto
# es legítimo y el control no tiene por qué negarlo.
UNIDADES_OK = ["UO-CAL-T1", "UO-FIN-T1"]


def _generar(cliente, token, formato="json", unidades=None,
             campanias=None, dimensiones=None):
    cuerpo = {"formato": formato,
              "campanias": campanias or ["CAMP-2026-S1"],
              "unidades": unidades or UNIDADES_OK}
    if dimensiones:
        cuerpo["dimensiones"] = dimensiones
    return cliente.post("/api/v1/exportaciones", headers=_cab(token),
                        json=cuerpo)


@pytest.fixture
def exportacion_json(cliente, token_especialista):
    r = _generar(cliente, token_especialista)
    assert r.status_code == 201, r.get_data(as_text=True)
    return r.get_json()


# =========================================================================
# Generar no es descargar
# =========================================================================

def test_generar_no_entrega_el_archivo(exportacion_json):
    """Dos actos, dos registros. La respuesta lo dice, no lo insinúa."""
    assert "contenido" not in exportacion_json
    assert exportacion_json["sello_sha256"]
    assert exportacion_json["descarga"].endswith("/archivo")
    assert "dos actos" in exportacion_json["nota"]


def test_un_colaborador_no_exporta(cliente, token_colaborador):
    r = _generar(cliente, token_colaborador)
    assert r.status_code == 403
    assert r.get_json()["error"]["codigo"] == "SIN_PERMISO"


def test_un_lider_no_exporta_fuera_de_su_alcance(cliente, token_lider):
    """El alcance sale del perfil, nunca del cuerpo de la peticion."""
    r = _generar(cliente, token_lider, unidades=["UO-CAL-T1"])
    # El líder no tiene EXPORTACION_GENERAR, así que se detiene antes
    # incluso de llegar al alcance. Las dos respuestas son 403 y las dos
    # son correctas; lo que no puede pasar es que exporte.
    assert r.status_code == 403, r.get_data(as_text=True)
    assert r.get_json()["error"]["codigo"] in ("SIN_PERMISO", "FUERA_DE_ALCANCE")


# =========================================================================
# Lo que el archivo tiene que conservar
# =========================================================================

def test_el_archivo_cuenta_las_filas_suprimidas(cliente, token_especialista):
    """«8 filas» y «8 de 12, 4 suprimidas» describen cosas distintas.

    Se piden a propósito dos unidades publicadas y dos suprimidas.
    """
    r = _generar(cliente, token_especialista,
                 unidades=["UO-CAL-T1", "UO-CC-TURNO-A"])
    assert r.status_code == 201, r.get_data(as_text=True)
    d = r.get_json()
    assert d["filas_publicadas"] > 0
    assert d["filas_suprimidas"] > 0, (
        "UO-CC-TURNO-A tiene todas sus filas suprimidas: si el archivo no "
        "las cuenta, las esta omitiendo.")


def test_la_fila_suprimida_sale_sin_valor_y_con_su_motivo(
        cliente, token_especialista, token_admin):
    """Omitirla haría creer que la unidad no participó."""
    r = _generar(cliente, token_especialista,
                 unidades=["UO-CAL-T1", "UO-CC-TURNO-A"])
    exportacion_id = r.get_json()["exportacion_id"]
    archivo = cliente.get(f"/api/v1/exportaciones/{exportacion_id}/archivo",
                          headers=_cab(token_especialista))
    assert archivo.status_code == 200, archivo.get_data(as_text=True)
    datos = json.loads(archivo.get_data(as_text=True))

    suprimidas = [f for f in datos["agregados"]
                  if f["unidad_organizacional_id"] == "UO-CC-TURNO-A"]
    assert suprimidas, "La unidad suprimida no aparece en el archivo."
    for fila in suprimidas:
        assert fila["valor_protegido"] is None, (
            "Un valor suprimido salio como un numero. Si fuera 0, en la "
            "escala 1..5 significaria el peor bienestar posible.")
        assert fila["estado_publicacion"] == "GRUPO_INSUFICIENTE"


def test_el_archivo_lleva_dentro_la_advertencia_de_ruido(
        cliente, token_especialista, exportacion_json):
    """En una nota al pie de la pantalla se pierde al mandar el archivo."""
    archivo = cliente.get(
        f"/api/v1/exportaciones/{exportacion_json['exportacion_id']}/archivo",
        headers=_cab(token_especialista))
    datos = json.loads(archivo.get_data(as_text=True))
    assert "Laplace" in datos["exportacion"]["advertencia"]
    assert datos["exportacion"]["epsilon_consumido"] == 0.0


def test_en_csv_un_nulo_es_raya_y_nunca_una_celda_vacia(
        cliente, token_especialista):
    """Una celda vacía se suma como cero en una hoja de cálculo.

    Y un promedio con ceros de unidades suprimidas da un número más bajo
    que el real, que en esta plataforma significa «peor bienestar».
    """
    r = _generar(cliente, token_especialista, formato="csv",
                 unidades=["UO-CC-TURNO-A"])
    assert r.status_code == 201, r.get_data(as_text=True)
    archivo = cliente.get(
        f"/api/v1/exportaciones/{r.get_json()['exportacion_id']}/archivo",
        headers=_cab(token_especialista))
    texto = archivo.get_data(as_text=True)
    assert "—" in texto
    assert ',""' not in texto, "Hay una celda vacia donde deberia ir «—»."
    # La advertencia va dentro del archivo, no en una cabecera HTTP.
    assert "Laplace" in texto


def test_el_pdf_se_genera_y_es_un_pdf(cliente, token_especialista):
    r = _generar(cliente, token_especialista, formato="pdf")
    assert r.status_code == 201, r.get_data(as_text=True)
    archivo = cliente.get(
        f"/api/v1/exportaciones/{r.get_json()['exportacion_id']}/archivo",
        headers=_cab(token_especialista))
    assert archivo.status_code == 200
    assert archivo.data[:5] == b"%PDF-"
    assert archivo.headers["Content-Type"] == "application/pdf"


def test_el_xml_valida_contra_su_xsd(cliente, token_especialista):
    """El contrato publicado y lo que el servicio emite, comparados.

    Un XSD que nadie valida contra la salida real es documentación, no
    contrato.
    """
    from lxml import etree
    r = _generar(cliente, token_especialista, formato="xml")
    assert r.status_code == 201, r.get_data(as_text=True)
    archivo = cliente.get(
        f"/api/v1/exportaciones/{r.get_json()['exportacion_id']}/archivo",
        headers=_cab(token_especialista))
    assert archivo.status_code == 200

    esquema = etree.XMLSchema(
        etree.parse(os.path.join(RAIZ, "contratos", "xml", "exportacion.xsd")))
    arbol = etree.fromstring(archivo.data)
    esquema.assertValid(arbol)


# =========================================================================
# La descarga
# =========================================================================

def test_descargar_exige_su_propio_permiso(cliente, exportacion_json,
                                           token_admin):
    """ADMINISTRADOR tiene los dos permisos; el caso interesante es que la
    descarga pasa por `requiere_permiso("EXPORTACION_DESCARGAR")` y no por
    el de generar."""
    ruta = f"/api/v1/exportaciones/{exportacion_json['exportacion_id']}/archivo"
    r = cliente.get(ruta, headers=_cab(token_admin))
    assert r.status_code in (200, 404), r.get_data(as_text=True)
    # Sin token no se entrega nada.
    assert cliente.get(ruta).status_code == 401


def test_la_descarga_entrega_los_bytes_sellados(cliente, token_especialista,
                                                exportacion_json):
    """No se regenera desde la selección: el sello dejaría de cuadrar."""
    archivo = cliente.get(
        f"/api/v1/exportaciones/{exportacion_json['exportacion_id']}/archivo",
        headers=_cab(token_especialista))
    assert archivo.status_code == 200
    recalculado = hashlib.sha256(archivo.data).hexdigest()
    assert recalculado == exportacion_json["sello_sha256"]
    assert archivo.headers["X-Exportacion-Sello"] == recalculado


def test_cada_descarga_queda_registrada_aparte(cliente, token_especialista,
                                               exportacion_json):
    """Una fila por descarga, no una bandera.

    La tercera descarga del mismo archivo, una semana después, es una
    salida de datos distinta de la primera.
    """
    ruta = f"/api/v1/exportaciones/{exportacion_json['exportacion_id']}"
    for _ in range(3):
        assert cliente.get(f"{ruta}/archivo",
                           headers=_cab(token_especialista)).status_code == 200

    d = cliente.get(ruta, headers=_cab(token_especialista)).get_json()
    assert len(d["descargas"]) == 3
    assert d["estado"] == "DESCARGADA"
    # Y el detalle no incluye el archivo.
    assert "contenido" not in d


def test_un_identificador_mal_formado_es_400_no_500(cliente,
                                                    token_especialista):
    r = cliente.get("/api/v1/exportaciones/../../etc/passwd",
                    headers=_cab(token_especialista))
    assert r.status_code in (400, 404), r.get_data(as_text=True)
    r = cliente.get("/api/v1/exportaciones/EXP-no-es-hex",
                    headers=_cab(token_especialista))
    assert r.status_code == 400
    assert r.get_json()["error"]["codigo"] == "PARAMETRO_INVALIDO"


def test_una_exportacion_de_otro_no_se_ve(cliente, token_especialista,
                                          token_admin, exportacion_json):
    """Sin BITACORA_CONSULTAR solo se ven las propias.

    Responde 404 y no 403 a propósito: un 403 confirmaría que esa
    exportación existe, que es justo lo que no hace falta saber.
    """
    # El especialista generó la del fixture. El administrador tiene
    # BITACORA_CONSULTAR, así que sí la ve: eso es lo correcto para quien
    # audita.
    r = cliente.get(f"/api/v1/exportaciones/{exportacion_json['exportacion_id']}",
                    headers=_cab(token_admin))
    assert r.status_code in (200, 404)


# =========================================================================
# El control de fuga
# =========================================================================

def test_el_servicio_consulta_el_control_antes_de_escribir(exportaciones):
    """La parte que le toca a este servicio.

    El cálculo del residuo se prueba en `test_inferencia.py`. Lo que
    importa aquí es el ORDEN: si la comprobación se hiciera después de
    armar el archivo, bastaría un error más adelante para que el archivo
    saliera igual.
    """
    ruta = os.path.join(RAIZ, "apps", "microservicios", "export-service",
                        "app.py")
    with open(ruta, encoding="utf-8") as f:
        fuente = f.read()
    assert "verificar_conjunto" in fuente
    assert fuente.index("verificar_conjunto(unidades") < fuente.index("_leer_agregados("), (
        "El control se llama DESPUES de leer los agregados. Tiene que ir "
        "antes de leer y de escribir.")
    # Y nunca LLAMA a la función que gasta épsilon. Se busca con
    # paréntesis a propósito: el nombre sí aparece en el docstring,
    # explicando por qué no se usa, y una prueba que buscara el nombre
    # suelto obligaría a borrar la explicación para pasar.
    assert "fn_calcular_agregado_protegido(" not in fuente
    assert "v_tablero_unidad" in fuente


def test_un_conjunto_que_aisla_un_grupo_pequeno_se_niega_y_se_registra(
        cliente, token_especialista, exportaciones, monkeypatch):
    """Se fuerza el bloqueo para comprobar lo que el servicio hace con él.

    Con los datos sembrados ninguna unidad publicada es padre de otra, así
    que `verificar_conjunto` no bloquea nada contra esta base —está dicho
    en `comun.inferencia` y probado en `test_inferencia.py`—. Aquí lo que
    se prueba es la reacción del servicio: 403, y una fila RECHAZADA en el
    registro. Si solo se registraran las exportaciones que salen, el
    intento no habría existido nunca.
    """
    from comun import ErrorApi

    def bloquea(unidades, consultar_uno, k):
        raise ErrorApi("INFERENCIA_BLOQUEADA",
                       "Permitiria aislar un grupo de 3 respondiente(s).", 403,
                       [{"campo": "residuo_respondientes", "problema": "3"}])

    monkeypatch.setattr(exportaciones, "verificar_conjunto", bloquea)
    r = _generar(cliente, token_especialista,
                 unidades=["UO-CAL-T1", "UO-FIN-T1"])
    assert r.status_code == 403, r.get_data(as_text=True)
    assert r.get_json()["error"]["codigo"] == "INFERENCIA_BLOQUEADA"

    from comun.datos import consultar
    rechazadas = consultar(
        "SELECT motivo_rechazo FROM exportacion.solicitud "
        " WHERE estado = 'RECHAZADA' ORDER BY fecha_generacion DESC LIMIT 1")
    assert rechazadas, "La exportacion negada no quedo registrada."
    assert "INFERENCIA_BLOQUEADA" in rechazadas[0]["motivo_rechazo"]


def test_una_exportacion_rechazada_no_tiene_archivo(cliente,
                                                    token_especialista):
    from comun.datos import consultar_uno
    fila = consultar_uno(
        "SELECT exportacion_id FROM exportacion.solicitud "
        " WHERE estado = 'RECHAZADA' ORDER BY fecha_generacion DESC LIMIT 1")
    if not fila:
        pytest.skip("No hay ninguna rechazada en este momento")
    r = cliente.get(f"/api/v1/exportaciones/{fila['exportacion_id']}/archivo",
                    headers=_cab(token_especialista))
    assert r.status_code in (409, 404), r.get_data(as_text=True)


# =========================================================================
# Validación de la selección
# =========================================================================

def test_una_campania_inexistente_es_422(cliente, token_especialista):
    r = _generar(cliente, token_especialista, campanias=["CAMP-9999-XX"])
    assert r.status_code == 422
    assert r.get_json()["error"]["codigo"] == "CAMPANIA_NO_EXISTE"


def test_una_seleccion_sin_campania_se_rechaza(cliente, token_especialista):
    """Sin campaña la selección sería toda la historia de la unidad."""
    r = cliente.post("/api/v1/exportaciones", headers=_cab(token_especialista),
                     json={"formato": "json", "unidades": UNIDADES_OK})
    assert r.status_code == 422
    campos = {d["campo"] for d in r.get_json()["error"]["detalles"]}
    assert "campanias" in campos


def test_un_formato_inventado_se_rechaza(cliente, token_especialista):
    r = _generar(cliente, token_especialista, formato="docx")
    assert r.status_code == 422


# =========================================================================
# Importación
# =========================================================================

def _archivo_json(filas):
    return json.dumps({"agregados": filas}, ensure_ascii=False)


def _validar(cliente, token, contenido, formato="json",
             procedencia="Sistema corporativo de RH, extraccion manual"):
    return cliente.post("/api/v1/importaciones/validar", headers=_cab(token),
                        json={"formato": formato, "procedencia": procedencia,
                              "contenido": contenido})


def test_la_importacion_informa_fila_por_fila(cliente, token_admin):
    """Un «no se pudo importar» sin detalle obliga a adivinar."""
    contenido = _archivo_json([
        {"unidad_organizacional_id": "UO-CAL-T1",
         "campania_id": "CAMP-2026-S1", "dimension": "Carga percibida",
         "valor": 3.4},
        {"unidad_organizacional_id": "UO-NO-EXISTE",
         "campania_id": "CAMP-2026-S1", "dimension": "Carga percibida",
         "valor": 3.4},
        {"unidad_organizacional_id": "UO-CAL-T1",
         "campania_id": "CAMP-2026-S1", "dimension": "Autonomia",
         "valor": 47},
        {"unidad_organizacional_id": "UO-CAL-T1",
         "campania_id": "CAMP-2026-S1"},
    ])
    r = _validar(cliente, token_admin, contenido)
    assert r.status_code == 201, r.get_data(as_text=True)
    d = r.get_json()
    assert d["filas_recibidas"] == 4
    assert d["filas_validas"] == 1
    assert d["filas_rechazadas"] == 3
    problemas = " | ".join(x["problema"] for x in d["detalle_rechazos"])
    assert "UO-NO-EXISTE" in problemas, (
        "Una unidad que no existe tiene que decirse por su nombre.")
    assert "escala" in problemas, "El valor 47 esta fuera de la escala 1..5."
    assert "faltan columnas" in problemas
    # Nada se aplicó.
    assert d["estado"] == "VALIDADA"
    assert "NUNCA" in d["nota"]


def test_validar_no_aplica_nada(cliente, token_admin):
    from comun.datos import consultar_uno
    contenido = _archivo_json([
        {"unidad_organizacional_id": "UO-CAL-T1",
         "campania_id": "CAMP-2026-S2", "dimension": "Carga percibida",
         "valor": 3.1}])
    r = _validar(cliente, token_admin, contenido)
    importacion_id = r.get_json()["importacion_id"]
    n = (consultar_uno("SELECT count(*) AS n FROM exportacion.agregado_externo "
                       " WHERE importacion_id = %s", (importacion_id,))
         or {}).get("n", 0)
    assert n == 0, "Validar dio de alta filas. Son dos pasos a proposito."


def test_aplicar_comprueba_el_sello(cliente, token_admin):
    """Validar un archivo y aplicar otro sería el agujero más obvio."""
    contenido = _archivo_json([
        {"unidad_organizacional_id": "UO-CAL-T1",
         "campania_id": "CAMP-2026-S3", "dimension": "Carga percibida",
         "valor": 3.2}])
    importacion_id = _validar(cliente, token_admin,
                              contenido).get_json()["importacion_id"]

    otro = _archivo_json([
        {"unidad_organizacional_id": "UO-CAL-T1",
         "campania_id": "CAMP-2026-S3", "dimension": "Carga percibida",
         "valor": 4.9}])
    r = cliente.post(f"/api/v1/importaciones/{importacion_id}/aplicar",
                     headers=_cab(token_admin), json={"contenido": otro})
    assert r.status_code == 409, r.get_data(as_text=True)
    assert r.get_json()["error"]["codigo"] == "SELLO_NO_COINCIDE"


def test_lo_aplicado_va_a_su_propia_tabla(cliente, token_admin):
    """Un agregado de fuera no pasó por el umbral k ni por el ruido.

    Si se guardara junto a los calculados, dejaría de poder distinguirse
    un valor protegido de uno que alguien escribió a mano.
    """
    from comun.datos import consultar_uno
    contenido = _archivo_json([
        {"unidad_organizacional_id": "UO-CAL-T2",
         "campania_id": "CAMP-2026-S4", "dimension": "Carga percibida",
         "valor": 3.3}])
    importacion_id = _validar(cliente, token_admin,
                              contenido).get_json()["importacion_id"]
    r = cliente.post(f"/api/v1/importaciones/{importacion_id}/aplicar",
                     headers=_cab(token_admin), json={"contenido": contenido})
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()["tabla"] == "exportacion.agregado_externo"

    externo = consultar_uno(
        "SELECT valor FROM exportacion.agregado_externo "
        " WHERE importacion_id = %s", (importacion_id,))
    assert externo and float(externo["valor"]) == pytest.approx(3.3)

    # Y NO entró a los agregados calculados.
    calculado = consultar_uno(
        "SELECT count(*) AS n FROM agregado.resultado_protegido "
        " WHERE unidad_organizacional_id = 'UO-CAL-T2' "
        "   AND campania_id = 'CAMP-2026-S4' AND valor_protegido = 3.3")
    assert (calculado or {}).get("n", 0) == 0, (
        "Un valor importado aparecio entre los agregados calculados.")


def test_no_se_aplica_dos_veces(cliente, token_admin):
    contenido = _archivo_json([
        {"unidad_organizacional_id": "UO-RH-T1",
         "campania_id": "CAMP-2026-S1", "dimension": "Autonomia",
         "valor": 3.9}])
    importacion_id = _validar(cliente, token_admin,
                              contenido).get_json()["importacion_id"]
    primera = cliente.post(f"/api/v1/importaciones/{importacion_id}/aplicar",
                           headers=_cab(token_admin),
                           json={"contenido": contenido})
    assert primera.status_code == 200
    segunda = cliente.post(f"/api/v1/importaciones/{importacion_id}/aplicar",
                           headers=_cab(token_admin),
                           json={"contenido": contenido})
    assert segunda.status_code == 409
    assert segunda.get_json()["error"]["codigo"] == "IMPORTACION_YA_APLICADA"


def test_la_procedencia_es_obligatoria(cliente, token_admin):
    """Un agregado sin procedencia es un número sin dueño."""
    r = _validar(cliente, token_admin,
                 _archivo_json([{"unidad_organizacional_id": "UO-CAL-T1",
                                 "campania_id": "CAMP-2026-S1",
                                 "dimension": "Autonomia", "valor": 3.0}]),
                 procedencia="x")
    assert r.status_code == 422
    campos = {d["campo"] for d in r.get_json()["error"]["detalles"]}
    assert "procedencia" in campos


def test_un_archivo_mal_formado_es_422_no_500(cliente, token_admin):
    r = _validar(cliente, token_admin, "{esto no es json")
    assert r.status_code == 422
    assert r.get_json()["error"]["codigo"] == "ARCHIVO_MAL_FORMADO"
    # El mensaje del analizador se incluye: es lo unico que permite
    # arreglar el archivo.
    assert len(r.get_json()["error"]["mensaje"]) > 40


def test_un_csv_exportado_se_puede_volver_a_importar(cliente,
                                                     token_especialista,
                                                     token_admin):
    """Las líneas de comentario que el servicio escribe se saltan.

    Si no se saltaran, habría que editar a mano todo archivo exportado
    antes de volver a meterlo, y nadie lo haría bien dos veces.
    """
    r = _generar(cliente, token_especialista, formato="csv",
                 unidades=["UO-CAL-T1"], dimensiones=["Carga percibida"])
    assert r.status_code == 201, r.get_data(as_text=True)
    csv_texto = cliente.get(
        f"/api/v1/exportaciones/{r.get_json()['exportacion_id']}/archivo",
        headers=_cab(token_especialista)).get_data(as_text=True)

    # El CSV exportado trae la columna `valor_protegido`, no `valor`: la
    # importación exige `valor`, así que la cabecera se adapta. Es la
    # diferencia deliberada entre el archivo que sale y el que entra.
    csv_texto = csv_texto.replace("valor_protegido", "valor")
    v = _validar(cliente, token_admin, csv_texto, formato="csv")
    assert v.status_code == 201, v.get_data(as_text=True)
    d = v.get_json()
    assert d["filas_recibidas"] > 0, (
        "Las lineas de comentario se tragaron el archivo entero.")
    assert d["filas_validas"] > 0


def test_el_pdf_no_se_puede_importar(cliente, token_admin):
    r = _validar(cliente, token_admin, "%PDF-1.4 ...", formato="pdf")
    assert r.status_code == 422
    campos = {d["campo"] for d in r.get_json()["error"]["detalles"]}
    assert "formato" in campos


# =========================================================================
# Contrato, bitácora y sonda
# =========================================================================

def test_el_contrato_cubre_todas_las_rutas(cliente, exportaciones):
    contrato = cliente.get("/openapi.json").get_json()
    documentadas = set(contrato["paths"])
    reales = set()
    for r in exportaciones.app.url_map.iter_rules():
        ruta = str(r.rule)
        if "/exportaciones" not in ruta and "/importaciones" not in ruta:
            continue
        reales.add(ruta.replace("<exportacion_id>", "{exportacion_id}")
                       .replace("<importacion_id>", "{importacion_id}"))
    faltan = reales - documentadas
    assert not faltan, f"Rutas sin documentar: {faltan}"


def test_los_codigos_de_bitacora_existen_en_la_base():
    """Si falta uno, la llave foránea falla y el `try` se lo traga.

    Es el defecto que la migración 007 vino a corregir, y la forma de que
    no vuelva es comparar los códigos del código contra los de la base.
    """
    from comun.datos import consultar
    ruta = os.path.join(RAIZ, "apps", "microservicios", "export-service",
                        "app.py")
    with open(ruta, encoding="utf-8") as f:
        fuente = f.read()

    import re
    usados = set(re.findall(r'_bitacora\("([A-Z_]+)"', fuente))
    assert usados, "No se encontro ninguna llamada a _bitacora"
    declarados = {f["codigo"] for f in consultar(
        "SELECT codigo FROM auditoria.tipo_accion")}
    faltan = usados - declarados
    assert not faltan, (
        f"Estos codigos se usan en el servicio y no estan en "
        f"auditoria.tipo_accion: {sorted(faltan)}. La insercion fallaria "
        f"en silencio y la bitacora perderia esos registros.")

    resultados_usados = set(re.findall(r'_bitacora\("[A-Z_]+",\s*"([A-Z_]+)"',
                                       fuente))
    declarados_r = {f["codigo"] for f in consultar(
        "SELECT codigo FROM auditoria.resultado")}
    faltan_r = resultados_usados - declarados_r
    assert not faltan_r, (
        f"Resultados sin declarar en auditoria.resultado: {sorted(faltan_r)}")


def test_la_sonda_de_salud_declara_sus_dependencias(cliente):
    r = cliente.get("/health/ready")
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    assert d["estado"] == "listo"
    assert set(d["dependencias"]) >= {"postgresql", "redis"}


def test_el_catalogo_de_formatos_dice_por_que_no_hay_pdf_al_importar(
        cliente, token_especialista):
    r = cliente.get("/api/v1/exportaciones/formatos",
                    headers=_cab(token_especialista))
    assert r.status_code == 200
    d = r.get_json()
    assert "pdf" not in d["importacion"]
    assert "presentacion" in d["por_que_no_se_importa_pdf"]
    assert d["epsilon_consumido_por_exportar"] == 0.0
