"""
Pruebas de documents-service y notifications-service (Integrante 3).

Cubren lo que pide el parcial para MongoDB —inserción, consulta,
actualización, agregación, indexación, filtrado y recuperación por
identificadores relacionados— y las dos restricciones de dominio que el
proyecto no puede romper.
"""
import pytest
from conftest import cab


# ---------------------------------------------------------------- salud
def test_salud_de_ambos(documentos, notificaciones):
    for cliente in (documentos, notificaciones):
        assert cliente.get("/health/live").status_code == 200
        r = cliente.get("/health/ready")
        assert r.status_code == 200, r.get_data(as_text=True)


def test_indexacion(documentos, notificaciones, token_admin):
    r = documentos.post("/api/v1/documentos/indices", headers=cab(token_admin))
    assert r.status_code == 200
    assert r.get_json()["total"] >= 4

    r2 = notificaciones.post("/api/v1/notificaciones/indices", headers=cab(token_admin))
    assert r2.status_code == 200
    assert r2.get_json()["total"] >= 3


# -------------------------------------------- la restricción de identidad
def test_mongodb_rechaza_el_identificador_de_empleado(documentos, token_auditor):
    """Si empleado_id llegara a MongoDB, la seudonimizacion dejaria de existir."""
    r = documentos.post("/api/v1/documentos", headers=cab(token_auditor), json={
        "tipo": "EVIDENCIA_CONSENTIMIENTO",
        "seudonimo_id": "SEUD-00001",
        "empleado_id": "EMP-00001",
        "contenido": {"version_aviso": "AVISO-v1", "decision": "ACEPTADO"},
    })
    assert r.status_code == 422
    assert r.get_json()["error"]["codigo"] == "CAMPO_PROHIBIDO"


def test_lo_rechaza_tambien_anidado(documentos, token_auditor):
    """La validacion recorre el documento completo, no solo el primer nivel."""
    r = documentos.post("/api/v1/documentos", headers=cab(token_auditor), json={
        "tipo": "REPORTE_ORGANIZACIONAL",
        "contenido": {"resumen": {"detalle": [{"empleado_id": "EMP-00002"}]}},
    })
    assert r.status_code == 422
    assert r.get_json()["error"]["codigo"] == "CAMPO_PROHIBIDO"
    assert r.get_json()["error"]["detalles"][0]["campo"] == \
        "contenido.resumen.detalle[0].empleado_id"


# -------------------------------------------- inserción, consulta, filtro
@pytest.fixture(scope="module")
def documento_creado(documentos, token_auditor):
    r = documentos.post("/api/v1/documentos", headers=cab(token_auditor), json={
        "tipo": "EVIDENCIA_CONSENTIMIENTO",
        "seudonimo_id": "SEUD-00001",
        "campania_id": "CAMP-2026-S1",
        "etiquetas": ["consentimiento", "nom035"],
        "contenido": {"version_aviso": "AVISO-v1", "decision": "ACEPTADO",
                      "canal": "portal web"},
    })
    assert r.status_code == 201, r.get_data(as_text=True)
    return r.get_json()["documento_id"]


def test_insercion_y_consulta(documentos, token_auditor, documento_creado):
    r = documentos.get(f"/api/v1/documentos/{documento_creado}",
                       headers=cab(token_auditor))
    assert r.status_code == 200
    d = r.get_json()
    assert d["tipo"] == "EVIDENCIA_CONSENTIMIENTO"
    assert d["contenido"]["decision"] == "ACEPTADO"
    assert len(d["hash_contenido"]) == 64     # sha256 en hexadecimal
    assert "_id" not in d                      # el id interno de Mongo no sale


def test_filtrado_por_tipo_y_etiqueta(documentos, token_auditor, documento_creado):
    r = documentos.get("/api/v1/documentos?tipo=EVIDENCIA_CONSENTIMIENTO&etiqueta=nom035",
                       headers=cab(token_auditor))
    assert r.status_code == 200
    ids = [d["documento_id"] for d in r.get_json()["documentos"]]
    assert documento_creado in ids


def test_filtro_rechaza_tipo_desconocido(documentos, token_auditor):
    r = documentos.get("/api/v1/documentos?tipo=INVENTADO", headers=cab(token_auditor))
    assert r.status_code == 400
    assert r.get_json()["error"]["codigo"] == "PARAMETRO_INVALIDO"


def test_una_evidencia_de_consentimiento_no_se_modifica(documentos, token_admin,
                                                        documento_creado):
    """Su valor como prueba depende de que nadie la pueda cambiar despues."""
    r = documentos.put(f"/api/v1/documentos/{documento_creado}",
                       headers=cab(token_admin),
                       json={"contenido": {"decision": "REVOCADO"}})
    assert r.status_code == 409
    assert r.get_json()["error"]["codigo"] == "DOCUMENTO_INMUTABLE"


def test_un_reporte_si_se_actualiza_y_sube_de_version(documentos, token_admin):
    creado = documentos.post("/api/v1/documentos", headers=cab(token_admin), json={
        "tipo": "REPORTE_ORGANIZACIONAL",
        "unidad_organizacional_id": "UO-CC-TURNO-B",
        "contenido": {"titulo": "Resumen de participacion", "secciones": 3},
    })
    assert creado.status_code == 201, creado.get_data(as_text=True)
    doc_id = creado.get_json()["documento_id"]

    r = documentos.put(f"/api/v1/documentos/{doc_id}", headers=cab(token_admin),
                       json={"contenido": {"titulo": "Resumen de participacion",
                                           "secciones": 4}})
    assert r.status_code == 200
    assert r.get_json()["version"] == 2


def test_integridad_contra_postgresql(documentos, token_admin):
    """Un documento que apunta a una unidad inexistente es basura silenciosa."""
    r = documentos.post("/api/v1/documentos", headers=cab(token_admin), json={
        "tipo": "REPORTE_ORGANIZACIONAL",
        "unidad_organizacional_id": "UO-NO-EXISTE",
        "contenido": {"titulo": "x"},
    })
    assert r.status_code == 422
    assert r.get_json()["error"]["codigo"] == "UNIDAD_NO_EXISTE"


def test_agregacion(documentos, token_admin, documento_creado):
    r = documentos.get("/api/v1/documentos/resumen", headers=cab(token_admin))
    assert r.status_code == 200
    assert r.get_json()["total_grupos"] >= 1


def test_recuperacion_por_identificador_relacionado(documentos, token_admin,
                                                    documento_creado):
    """Cruce real entre MongoDB y PostgreSQL por campania_id."""
    r = documentos.get("/api/v1/documentos/por-campania/CAMP-2026-S1",
                       headers=cab(token_admin))
    assert r.status_code == 200
    d = r.get_json()
    assert d["campania"]["campania_id"] == "CAMP-2026-S1"
    assert d["campania"]["nombre"]            # vino de PostgreSQL
    assert d["total_documentos"] >= 1         # vinieron de MongoDB


def test_campania_inexistente(documentos, token_admin):
    r = documentos.get("/api/v1/documentos/por-campania/CAMP-NO-EXISTE",
                       headers=cab(token_admin))
    assert r.status_code == 404
    assert r.get_json()["error"]["codigo"] == "CAMPANIA_NO_EXISTE"


# ------------------------------------------------------- notificaciones
def test_una_notificacion_no_puede_llevar_cifras(notificaciones, token_especialista):
    """Publicar un valor por esta via saltaria el presupuesto de epsilon."""
    r = notificaciones.post("/api/v1/notificaciones", headers=cab(token_especialista),
                            json={"tipo": "CONDICION_DETECTADA",
                                  "titulo": "Condicion detectada en tu unidad",
                                  "mensaje": "La carga percibida bajo a 2.9 puntos",
                                  "unidad_organizacional_id": "UO-CC-TURNO-B"})
    assert r.status_code == 422
    assert r.get_json()["error"]["codigo"] == "CIFRA_NO_PERMITIDA"


def test_envio_y_bandeja(notificaciones, token_especialista, token_colaborador):
    r = notificaciones.post("/api/v1/notificaciones", headers=cab(token_especialista),
                            json={"tipo": "CAMPANIA_ABIERTA",
                                  "titulo": "Hay una campania abierta",
                                  "mensaje": "Tienes una encuesta pendiente de responder",
                                  "destinatarios": ["USR-00001"]})
    assert r.status_code == 201, r.get_data(as_text=True)
    assert r.get_json()["enviadas"] == 1

    bandeja = notificaciones.get("/api/v1/notificaciones/mias",
                                 headers=cab(token_colaborador))
    assert bandeja.status_code == 200
    d = bandeja.get_json()
    assert d["sin_leer"] >= 1
    assert d["notificaciones"][0]["destinatario_usuario_id"] == "USR-00001"


def test_nadie_marca_como_leida_la_notificacion_de_otro(notificaciones,
                                                        token_especialista,
                                                        token_colaborador):
    envio = notificaciones.post("/api/v1/notificaciones", headers=cab(token_especialista),
                                json={"tipo": "RECORDATORIO_ENCUESTA",
                                      "titulo": "Recordatorio de encuesta",
                                      "mensaje": "Te falta responder la campania abierta",
                                      "destinatarios": ["USR-00001"]})
    assert envio.status_code == 201

    bandeja = notificaciones.get("/api/v1/notificaciones/mias?solo_sin_leer=true",
                                 headers=cab(token_colaborador))
    nid = bandeja.get_json()["notificaciones"][0]["notificacion_id"]

    # El especialista no es el destinatario: no debe poder marcarla.
    ajeno = notificaciones.put(f"/api/v1/notificaciones/{nid}/leida",
                               headers=cab(token_especialista))
    assert ajeno.status_code == 404

    propio = notificaciones.put(f"/api/v1/notificaciones/{nid}/leida",
                                headers=cab(token_colaborador))
    assert propio.status_code == 200
    assert propio.get_json()["leida"] is True


def test_contador_sin_leer(notificaciones, token_colaborador):
    r = notificaciones.get("/api/v1/notificaciones/sin-leer", headers=cab(token_colaborador))
    assert r.status_code == 200
    assert r.get_json()["origen"] in ("redis", "mongodb")


def test_resumen_de_notificaciones(notificaciones, token_admin):
    r = notificaciones.get("/api/v1/notificaciones/resumen", headers=cab(token_admin))
    assert r.status_code == 200
    d = r.get_json()
    assert len(d["tipos_disponibles"]) == 5
    assert all("porcentaje_lectura" in x for x in d["resumen"])


# ------------------------------------------------------------------ XML
def test_documentos_responde_xml(documentos, token_auditor, documento_creado):
    from lxml import etree
    r = documentos.get("/api/v1/documentos?tamano=2",
                       headers=cab(token_auditor, xml=True))
    assert r.status_code == 200
    raiz = etree.fromstring(r.get_data())
    ns = {"b": "http://nexum.com.mx/bienestar/v1"}
    assert raiz.findall(".//b:documentos/b:documento", ns)


def test_notificaciones_responde_xml(notificaciones, token_colaborador):
    from lxml import etree
    r = notificaciones.get("/api/v1/notificaciones/mias",
                           headers=cab(token_colaborador, xml=True))
    assert r.status_code == 200
    raiz = etree.fromstring(r.get_data())
    ns = {"b": "http://nexum.com.mx/bienestar/v1"}
    assert raiz.find(".//b:paginacion/b:tamano", ns) is not None
