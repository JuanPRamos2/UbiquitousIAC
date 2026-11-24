"""
Pruebas de queries-service y reports-service.

Las dos garantías que estas pruebas existen para defender no se ven en la
firma de los endpoints, así que hay que comprobarlas a propósito:

  * ninguno de los dos servicios consume presupuesto de épsilon, por mucho
    que se les llame;
  * un reporte no esconde las filas suprimidas.

Lo demás son las cosas de siempre: autenticación, permisos, paginación,
caché y los dos formatos de salida.
"""
import pytest
from conftest import cab


# ------------------------------------------------------------------ salud
def test_salud_de_ambos(consultas, reportes):
    for cliente in (consultas, reportes):
        assert cliente.get("/health/live").status_code == 200
        r = cliente.get("/health/ready")
        assert r.status_code == 200, r.get_data(as_text=True)


def test_ambos_publican_su_contrato(consultas, reportes):
    for cliente in (consultas, reportes):
        c = cliente.get("/openapi.json")
        assert c.status_code == 200
        contrato = c.get_json()
        assert contrato["openapi"] == "3.0.3"
        assert contrato["components"]["securitySchemes"]["bearerAuth"]
        # Las siete respuestas de error son las mismas en los ocho servicios.
        assert len(contrato["components"]["responses"]) == 7
        assert cliente.get("/docs").status_code == 200


# ---------------------------------------------------- sin token no se entra
def test_sin_token_nada(consultas, reportes):
    assert consultas.get("/api/v1/consultas/presupuesto").status_code == 401
    assert reportes.get("/api/v1/reportes/catalogo").status_code == 401


# =========================================================================
# queries-service
# =========================================================================

def test_presupuesto_se_consulta_sin_gastar_epsilon(consultas, token_admin):
    """La prueba central del servicio.

    Se lee el presupuesto, se piden consultas, y se vuelve a leer el
    presupuesto: el épsilon consumido tiene que ser EXACTAMENTE el mismo.
    Si queries-service invocara fn_calcular_agregado_protegido, este número
    subiría en cada llamada y la campaña se quedaría sin poder publicar.
    """
    antes = consultas.get("/api/v1/consultas/presupuesto", headers=cab(token_admin))
    assert antes.status_code == 200
    elementos = antes.get_json()["elementos"]
    assert elementos, "la base de demostracion debe traer presupuesto sembrado"
    gasto_antes = sum(float(e["epsilon_consumido"]) for e in elementos)

    for _ in range(5):
        assert consultas.get("/api/v1/consultas/participacion",
                             headers=cab(token_admin)).status_code == 200
        assert consultas.get("/api/v1/consultas/catalogo/resumen",
                             headers=cab(token_admin)).status_code == 200

    despues = consultas.get("/api/v1/consultas/presupuesto?pagina=1",
                            headers=cab(token_admin))
    gasto_despues = sum(float(e["epsilon_consumido"])
                        for e in despues.get_json()["elementos"])
    assert gasto_despues == gasto_antes, (
        "consultar el tablero gasto presupuesto de privacidad: el servicio "
        "esta recalculando agregados en lugar de leer los publicados")


def test_la_cache_responde_la_segunda_vez(consultas, token_admin):
    primera = consultas.get("/api/v1/consultas/participacion",
                            headers=cab(token_admin))
    segunda = consultas.get("/api/v1/consultas/participacion",
                            headers=cab(token_admin))
    assert primera.status_code == segunda.status_code == 200
    # La cabecera permite demostrar la cache desde el navegador.
    assert segunda.headers.get("X-Cache") == "ACIERTO", segunda.headers
    assert segunda.get_json()["desde_cache"] is True
    # Y los datos son los mismos: una cache que devuelve otra cosa es un error.
    assert segunda.get_json()["elementos"] == primera.get_json()["elementos"]


def test_la_invalidacion_vacia_la_cache(consultas, token_admin):
    consultas.get("/api/v1/consultas/participacion", headers=cab(token_admin))
    r = consultas.post("/api/v1/consultas/cache/invalidar",
                       headers=cab(token_admin), json={"recurso": "participacion"})
    assert r.status_code == 200
    assert r.get_json()["entradas_borradas"] >= 1
    # Tras invalidar, la siguiente consulta vuelve a ir a la base.
    siguiente = consultas.get("/api/v1/consultas/participacion",
                              headers=cab(token_admin))
    assert siguiente.headers.get("X-Cache") == "FALLO"


def test_el_estado_de_la_cache_trae_numeros(consultas, token_admin):
    r = consultas.get("/api/v1/consultas/cache/estado", headers=cab(token_admin))
    assert r.status_code == 200
    cuerpo = r.get_json()
    assert cuerpo["redis_disponible"] is True
    assert "participacion" in cuerpo["por_recurso"]
    metrica = cuerpo["por_recurso"]["participacion"]
    assert metrica["aciertos"] + metrica["fallos"] > 0
    assert metrica["ttl_segundos"] > 0


def test_recurso_desconocido_se_rechaza(consultas, token_admin):
    r = consultas.post("/api/v1/consultas/cache/invalidar",
                       headers=cab(token_admin), json={"recurso": "inventado"})
    assert r.status_code == 400
    assert r.get_json()["error"]["codigo"] == "PARAMETRO_INVALIDO"


def test_una_unidad_inexistente_da_404_y_no_una_lista_vacia(consultas,
                                                             token_especialista):
    """Una lista vacía deja creer que la unidad existe y no tuvo resultados.

    Lo que pasa en realidad es que el identificador está mal escrito, y eso
    se dice con un 404.
    """
    r = consultas.get("/api/v1/consultas/tablero/unidad/UO-NO-EXISTE",
                      headers=cab(token_especialista))
    assert r.status_code == 404
    assert r.get_json()["error"]["codigo"] == "NO_ENCONTRADO"


def test_el_lider_no_ve_el_tablero_de_otra_unidad(consultas, token_lider):
    """El alcance se resuelve contra la jerarquía, no contra el token.

    El líder de UO-CC-TURNO-B pide el tablero de UO-LOG-TURNO-A, que existe
    y no está en su subárbol: 403. Si el alcance se tomara del parámetro,
    bastaría cambiar la URL para ver el tablero de otra área.
    """
    r = consultas.get("/api/v1/consultas/tablero/unidad/UO-LOG-TURNO-A",
                      headers=cab(token_lider))
    assert r.status_code == 403
    assert r.get_json()["error"]["codigo"] == "FUERA_DE_ALCANCE"


def test_el_lider_si_ve_su_propia_unidad(consultas, token_lider):
    r = consultas.get("/api/v1/consultas/tablero/unidad/UO-CC-TURNO-B",
                      headers=cab(token_lider))
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()["filas"]


def test_la_tendencia_exige_la_unidad(consultas, token_especialista):
    r = consultas.get("/api/v1/consultas/tendencia", headers=cab(token_especialista))
    assert r.status_code == 400
    assert r.get_json()["error"]["codigo"] == "PARAMETRO_FALTANTE"


def test_el_colaborador_no_consulta_tableros(consultas, token_colaborador):
    r = consultas.get("/api/v1/consultas/presupuesto", headers=cab(token_colaborador))
    assert r.status_code == 403
    assert r.get_json()["error"]["codigo"] == "SIN_PERMISO"


# =========================================================================
# reports-service
# =========================================================================

def test_el_catalogo_se_filtra_por_permisos(reportes, token_admin,
                                            token_colaborador):
    r = reportes.get("/api/v1/reportes/catalogo", headers=cab(token_admin))
    assert r.status_code == 200
    tipos_admin = {e["tipo"] for e in r.get_json()["elementos"]}
    assert "BITACORA_AUDITORIA" in tipos_admin

    # Un colaborador no tiene ningun permiso de reportes: ni siquiera debe
    # ver el nombre del reporte de bitacora.
    r2 = reportes.get("/api/v1/reportes/catalogo", headers=cab(token_colaborador))
    assert r2.status_code == 403


def test_generar_sellar_descargar_y_verificar(reportes, token_admin):
    """El ciclo completo del servicio, de extremo a extremo."""
    r = reportes.post("/api/v1/reportes", headers=cab(token_admin),
                      json={"tipo": "PRESUPUESTO_EPSILON"})
    assert r.status_code == 201, r.get_data(as_text=True)
    reporte = r.get_json()
    assert reporte["reporte_id"].startswith("RPT-")
    assert len(reporte["sello_sha256"]) == 64
    assert reporte["total_filas"] > 0
    # El campo esta en la respuesta como prueba, por reporte, de que
    # generarlo no gasto privacidad.
    assert reporte["epsilon_consumido"] == 0

    rid = reporte["reporte_id"]

    # Los tres formatos salen del MISMO documento guardado.
    j = reportes.get(f"/api/v1/reportes/{rid}/contenido?formato=json",
                     headers=cab(token_admin))
    c = reportes.get(f"/api/v1/reportes/{rid}/contenido?formato=csv",
                     headers=cab(token_admin))
    x = reportes.get(f"/api/v1/reportes/{rid}/contenido?formato=xml",
                     headers=cab(token_admin))
    for respuesta in (j, c, x):
        assert respuesta.status_code == 200
        assert respuesta.headers["X-Reporte-Sello"] == reporte["sello_sha256"]
        assert "attachment" in respuesta.headers["Content-Disposition"]

    # El CSV va con comillas en todos los campos y con BOM para Excel.
    texto = c.get_data(as_text=True)
    assert texto.startswith("﻿\"")
    assert texto.count("\r\n") == reporte["total_filas"] + 1   # + encabezado

    # Verificar el sello: coincide y el documento guardado esta intacto.
    v = reportes.post(f"/api/v1/reportes/{rid}/verificar", headers=cab(token_admin),
                      json={"sello_sha256": reporte["sello_sha256"]})
    assert v.status_code == 200
    assert v.get_json()["coincide"] is True
    assert v.get_json()["integro"] is True


def test_un_sello_ajeno_no_coincide(reportes, token_admin):
    r = reportes.post("/api/v1/reportes", headers=cab(token_admin),
                      json={"tipo": "PARTICIPACION"})
    rid = r.get_json()["reporte_id"]
    v = reportes.post(f"/api/v1/reportes/{rid}/verificar", headers=cab(token_admin),
                      json={"sello_sha256": "f" * 64})
    assert v.status_code == 200
    assert v.get_json()["coincide"] is False
    # Pero el documento guardado sigue intacto: una cosa es que el archivo
    # que trajo el auditor no sea el nuestro, y otra que el nuestro este mal.
    assert v.get_json()["integro"] is True


def test_el_mismo_reporte_da_el_mismo_sello(reportes, token_admin):
    """Dos generaciones sobre los mismos datos tienen que sellar igual.

    Si el sello cambiara entre generaciones (por una fecha metida en el
    contenido canónico, por ejemplo) no serviría para confrontar nada.
    """
    a = reportes.post("/api/v1/reportes", headers=cab(token_admin),
                      json={"tipo": "PARTICIPACION"}).get_json()
    b = reportes.post("/api/v1/reportes", headers=cab(token_admin),
                      json={"tipo": "PARTICIPACION"}).get_json()
    assert a["reporte_id"] != b["reporte_id"]
    assert a["sello_sha256"] == b["sello_sha256"]


def test_las_supresiones_se_exportan_con_su_motivo(reportes, token_admin):
    """Un reporte no esconde lo que no se publicó.

    La base de demostración trae agregados suprimidos. El reporte tiene que
    traerlos, con el motivo, y contarlos en los metadatos: un CSV que los
    omitiera haría creer que la campaña tuvo menos unidades de las que tuvo.
    """
    r = reportes.post("/api/v1/reportes", headers=cab(token_admin),
                      json={"tipo": "SUPRESIONES"})
    assert r.status_code == 201
    cuerpo = r.get_json()
    assert cuerpo["total_filas"] > 0
    assert cuerpo["filas_suprimidas"] == cuerpo["total_filas"]
    assert "motivo_supresion" in cuerpo["columnas"]
    assert "explicacion" in cuerpo["columnas"]

    contenido = reportes.get(
        f"/api/v1/reportes/{cuerpo['reporte_id']}/contenido",
        headers=cab(token_admin)).get_json()
    motivos = {f["motivo_supresion"] for f in contenido["filas"]}
    assert motivos <= {"GRUPO_INSUFICIENTE", "PRESUPUESTO_PRIVACIDAD_AGOTADO"}
    # Ninguna fila suprimida trae valor: si lo trajera, la supresion seria
    # decorativa.
    assert all("valor_protegido" not in f for f in contenido["filas"])


def test_el_tipo_obligatorio_se_exige(reportes, token_especialista):
    """TABLERO_CAMPANIA exige la campaña: sin ella el reporte no significa nada.

    Se usa el especialista porque es quien tiene AGREGADO_UNIDAD: con otro
    perfil la respuesta sería un 403 y no se estaría probando la validación.
    """
    r = reportes.post("/api/v1/reportes", headers=cab(token_especialista),
                      json={"tipo": "TABLERO_CAMPANIA"})
    assert r.status_code == 422
    assert r.get_json()["error"]["codigo"] == "VALIDACION"
    assert r.get_json()["error"]["detalles"][0]["campo"] == "parametro"


def test_tipo_desconocido(reportes, token_admin):
    r = reportes.post("/api/v1/reportes", headers=cab(token_admin),
                      json={"tipo": "LO_QUE_SEA"})
    assert r.status_code == 404
    assert r.get_json()["error"]["codigo"] == "TIPO_DESCONOCIDO"


def test_sin_datos_no_se_entrega_un_reporte_vacio(reportes, token_auditor):
    """Un archivo sin filas se confunde con una campaña sin supresiones."""
    r = reportes.post("/api/v1/reportes", headers=cab(token_auditor),
                      json={"tipo": "SUPRESIONES", "parametro": "CAMP-NO-EXISTE"})
    assert r.status_code == 404
    assert r.get_json()["error"]["codigo"] == "SIN_DATOS"


def test_el_permiso_se_verifica_por_tipo_no_solo_por_servicio(reportes,
                                                              token_auditor):
    """La segunda verificación de permiso, la que suele faltar.

    El auditor tiene BITACORA_CONSULTAR, así que el decorador lo deja
    entrar al servicio. Pero no tiene INTERVENCION_* ni
    RECOMENDACION_CONSULTAR, de modo que el reporte de intervenciones tiene
    que negarse en el cuerpo del endpoint.
    """
    r = reportes.post("/api/v1/reportes", headers=cab(token_auditor),
                      json={"tipo": "INTERVENCIONES"})
    assert r.status_code == 403
    assert r.get_json()["error"]["codigo"] == "PERMISO_INSUFICIENTE"


def test_el_listado_solo_muestra_los_tipos_permitidos(reportes, token_admin,
                                                      token_auditor):
    reportes.post("/api/v1/reportes", headers=cab(token_admin),
                  json={"tipo": "PRESUPUESTO_EPSILON"})
    r = reportes.get("/api/v1/reportes?tamano=50", headers=cab(token_auditor))
    assert r.status_code == 200
    cuerpo = r.get_json()
    assert cuerpo["paginacion"]["total"] >= 1
    permitidos = {"PARTICIPACION", "PRESUPUESTO_EPSILON", "SUPRESIONES",
                  "BITACORA_AUDITORIA"}
    assert {e["tipo"] for e in cuerpo["elementos"]} <= permitidos
    # El listado no arrastra las filas: seria mandar miles por pagina.
    assert all("filas" not in e for e in cuerpo["elementos"])


def test_un_tipo_ajeno_en_el_filtro_se_niega(reportes, token_auditor):
    r = reportes.get("/api/v1/reportes?tipo=INTERVENCIONES",
                     headers=cab(token_auditor))
    assert r.status_code == 403


def test_reporte_inexistente(reportes, token_admin):
    r = reportes.get("/api/v1/reportes/RPT-000000000000", headers=cab(token_admin))
    assert r.status_code == 404


def test_formato_no_soportado(reportes, token_admin):
    """`pdf` ya NO sirve de ejemplo: la especificacion lo exige y existe."""
    rid = reportes.post("/api/v1/reportes", headers=cab(token_admin),
                        json={"tipo": "PARTICIPACION"}).get_json()["reporte_id"]
    r = reportes.get(f"/api/v1/reportes/{rid}/contenido?formato=docx",
                     headers=cab(token_admin))
    assert r.status_code == 400
    assert r.get_json()["error"]["codigo"] == "PARAMETRO_INVALIDO"
    # El mensaje nombra los validos: sin eso, quien lo recibe adivina.
    for formato in ("json", "csv", "xml", "xlsx", "pdf"):
        assert formato in r.get_json()["error"]["mensaje"]


def test_generar_un_reporte_queda_en_la_bitacora(reportes, token_admin):
    """La bitácora tiene llave foránea contra auditoria.tipo_accion.

    Si los códigos de reports-service no estuvieran declarados en la
    migración 005, la inserción fallaría en silencio y la operación no
    dejaría rastro. Se comprueba contra la base, no contra el log.
    """
    import os

    import psycopg2
    reportes.post("/api/v1/reportes", headers=cab(token_admin),
                  json={"tipo": "PARTICIPACION"})
    cn = psycopg2.connect(host=os.environ["PG_HOST"], dbname=os.environ["PG_BASE"],
                          user=os.environ["PG_USUARIO"],
                          password=os.environ["PG_CLAVE"])
    with cn, cn.cursor() as cur:
        cur.execute("SELECT count(*) FROM auditoria.bitacora "
                    " WHERE accion = 'REPORTE_GENERADO'")
        generados = cur.fetchone()[0]
    cn.close()
    assert generados >= 1, ("reports-service no pudo escribir en la bitacora: "
                            "falta aplicar la migracion 005")


# =========================================================================
# El periodo de la serie
# =========================================================================
# La tabla del profesor pide para queries-service «consultas agregadas
# seguras por campaña, periodo y unidad». Por campaña y por unidad ya
# estaba; el periodo se acota con un rango de campañas, porque en este
# sistema la campaña ES el periodo de medición: cada una cubre un
# semestre y `secuencia` las ordena.

def test_la_tendencia_se_puede_acotar_a_un_rango_de_campanias(
        consultas, token_especialista):
    completa = consultas.get(
        "/api/v1/consultas/tendencia?unidad_organizacional_id=UO-CC-TURNO-B",
        headers=cab(token_especialista))
    assert completa.status_code == 200, completa.get_data(as_text=True)
    todos = completa.get_json()["puntos"]
    assert todos, "La unidad de prueba no tiene serie; revisa la semilla."

    acotada = consultas.get(
        "/api/v1/consultas/tendencia?unidad_organizacional_id=UO-CC-TURNO-B"
        "&desde_campania=CAMP-2026-S2&hasta_campania=CAMP-2026-S3",
        headers=cab(token_especialista))
    assert acotada.status_code == 200, acotada.get_data(as_text=True)
    recortados = acotada.get_json()["puntos"]

    assert len(recortados) < len(todos), (
        "El rango no recorto nada. Si la serie completa y la acotada traen "
        "lo mismo, el filtro no se esta aplicando o la caché devolvio la "
        "serie entera.")
    assert {p["campania_id"] for p in recortados} <= {"CAMP-2026-S2",
                                                      "CAMP-2026-S3"}


def test_el_rango_entra_en_la_clave_de_cache(consultas, token_especialista):
    """Si no entrara, el filtro parecería no funcionar y nadie sabría por qué.

    La primera consulta deja guardada la serie completa de la unidad; la
    siguiente, acotada, recibiría esa misma serie entera desde la caché.
    Esta prueba pide primero la completa a propósito, para que la caché
    esté caliente cuando llegue la acotada.
    """
    ruta = "/api/v1/consultas/tendencia?unidad_organizacional_id=UO-CC-TURNO-B"
    consultas.get(ruta, headers=cab(token_especialista))          # calienta
    consultas.get(ruta, headers=cab(token_especialista))          # acierto

    acotada = consultas.get(ruta + "&hasta_campania=CAMP-2026-S1",
                            headers=cab(token_especialista))
    assert acotada.status_code == 200
    campanias = {p["campania_id"] for p in acotada.get_json()["puntos"]}
    assert campanias <= {"CAMP-2026-S1"}, (
        f"Llegaron campanias fuera del rango: {campanias}. La clave de "
        f"cache no distingue el rango.")


def test_una_campania_inexistente_en_el_rango_es_422(consultas,
                                                     token_especialista):
    """Y no una serie vacía.

    Una serie vacía deja creer que la unidad no tuvo resultados en ese
    periodo, cuando lo que pasa es que el identificador está mal escrito.
    """
    r = consultas.get(
        "/api/v1/consultas/tendencia?unidad_organizacional_id=UO-CC-TURNO-B"
        "&desde_campania=CAMP-QUE-NO-EXISTE",
        headers=cab(token_especialista))
    assert r.status_code == 422, r.get_data(as_text=True)
    assert r.get_json()["error"]["codigo"] == "CAMPANIA_NO_EXISTE"


def test_el_rango_se_corta_por_secuencia_y_no_por_texto(consultas,
                                                        token_especialista):
    """Ordenar por el texto del identificador rompería con diez campañas.

    'CAMP-2026-S10' como cadena va antes de 'CAMP-2026-S2', así que un
    recorte por texto saldría al revés. Se comprueba que la serie devuelta
    viene ordenada por `secuencia` creciente.
    """
    r = consultas.get(
        "/api/v1/consultas/tendencia?unidad_organizacional_id=UO-CC-TURNO-B",
        headers=cab(token_especialista))
    secuencias = [p["secuencia"] for p in r.get_json()["puntos"]]
    assert secuencias == sorted(secuencias), secuencias
