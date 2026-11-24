"""
sync-service — sincronización con red intermitente.

LA PRUEBA QUE JUSTIFICA EL ARCHIVO
----------------------------------
Reenviar un lote ya aplicado **no duplica nada y devuelve lo mismo**.

Es todo el servicio en una frase. Con red intermitente el cliente no puede
distinguir «no llegó» de «llegó y se aplicó, pero la respuesta se perdió al
volver», así que reenvía siempre; si reenviar duplicara, cada corte de red
metería respuestas falsas en los agregados.

Las otras tres que importan:

  · que un renglón mal formado NO tumbe el lote (el cliente que capturó los
    otros treinta y nueve sin red no tiene cómo recuperarlos);
  · que un conflicto conserve la PRIMERA respuesta, porque esa quizá ya
    entró en un agregado publicado;
  · que el servidor distinga lo reintentable de lo que no, porque si no, el
    cliente reenvía para siempre algo imposible o abandona algo que sí
    habría pasado.

NOTA SOBRE REPETIBILIDAD
------------------------
Estas pruebas escriben autoreportes de verdad, y una respuesta consume el
par (seudónimo, campaña) para siempre: la regla de negocio es una
respuesta por campaña. Así que cada corrida toma un seudónimo que todavía
no haya contestado, y cada identificador de operación lleva un sufijo
único. Sin las dos cosas, la segunda corrida vería YA_RESPONDIDA y
DUPLICADA donde la primera vio APLICADA, y las pruebas fallarían sin que
nada estuviera roto.
"""
import uuid

import pytest

CAMPANIA_ABIERTA = "CAMP-2026-S5"
CAMPANIA_CERRADA = "CAMP-2026-S1"
VALORES = {"R-01": 4, "R-02": 3, "R-03": 4, "R-04": 3, "R-05": 5}


@pytest.fixture(scope="module")
def sincronizacion():
    from conftest import _cargar
    modulo = _cargar("sync-service", "svc_sync")
    modulo.app.config["TESTING"] = True
    return modulo


@pytest.fixture
def cliente(sincronizacion):
    return sincronizacion.app.test_client()


@pytest.fixture
def corrida():
    """Sufijo único por prueba, para que los identificadores no choquen
    entre corridas de la suite."""
    return uuid.uuid4().hex[:12]


@pytest.fixture
def seudonimos_libres():
    """Seudónimos con consentimiento vigente que aún no contestaron.

    Se consultan en cada prueba y no se fijan en una constante: una
    respuesta consume el par (seudónimo, campaña) de forma permanente, así
    que una constante haría que la suite dejara de ser repetible desde la
    segunda corrida.

    POR QUÉ NO SE CONSULTA `autoreporte.respuesta`
    ----------------------------------------------
    Sería lo directo y **no se puede**: el rol de la aplicación no tiene
    SELECT sobre esa tabla, a propósito, y es una de las garantías del
    proyecto. El primer intento de este archivo la consultaba y fallaba
    con «permission denied for table respuesta», que es la garantía
    funcionando.

    Así que se descuentan los seudónimos que ya consumió la
    sincronización, leídos de `sincronizacion.operacion`, que sí es
    legible. Alcanza porque la campaña abierta no trae respuestas en la
    semilla —las 968 sembradas son de las cuatro campañas cerradas—, así
    que en este entorno la única vía que consume pares con la campaña
    abierta es esta. Si alguien contestara por el portal entre dos
    corridas, la prueba lo vería como un conflicto, y el mensaje de fallo
    lo diría.
    """
    from comun.datos import consultar
    filas = consultar(
        "SELECT v.seudonimo_id FROM consentimiento.v_estado_vigente v "
        " WHERE v.estado = 'ACEPTADO' "
        "   AND NOT EXISTS (SELECT 1 FROM sincronizacion.operacion o "
        "                    WHERE o.seudonimo_id = v.seudonimo_id "
        "                      AND o.campania_id = %s "
        "                      AND o.estado = 'APLICADA') "
        " ORDER BY random() LIMIT 10", (CAMPANIA_ABIERTA,))
    libres = [f["seudonimo_id"] for f in filas]
    if len(libres) < 4:
        pytest.skip("No quedan seudonimos sin respuesta en la campania "
                    "abierta; recarga la base para volver a correr esto.")
    return libres


def _cab(token):
    return {"Authorization": f"Bearer {token}"}


def _operacion(clave, seudonimo, campania=CAMPANIA_ABIERTA, valores=None):
    return {"operacion_cliente_id": clave, "tipo": "AUTOREPORTE",
            "seudonimo_id": seudonimo, "campania_id": campania,
            "valores": valores if valores is not None else dict(VALORES)}


def _enviar(cliente, token, lote_id, operaciones, origen="MOVIL"):
    return cliente.post("/api/v1/sincronizacion/lotes", headers=_cab(token),
                        json={"lote_cliente_id": lote_id, "origen": origen,
                              "operaciones": operaciones})


# =========================================================================
# La prueba que justifica el archivo
# =========================================================================

def test_reenviar_el_mismo_lote_no_duplica_y_devuelve_lo_mismo(
        cliente, token_colaborador, corrida, seudonimos_libres):
    """El caso central: el cliente reenvía porque no sabe si llegó.

    Si reenviar duplicara, cada corte de red metería respuestas falsas en
    los agregados.
    """
    lote = f"lote-{corrida}"
    ops = [_operacion(f"op-{corrida}-1", seudonimos_libres[0]),
           _operacion(f"op-{corrida}-2", seudonimos_libres[1])]

    primera = _enviar(cliente, token_colaborador, lote, ops)
    assert primera.status_code == 200, primera.get_data(as_text=True)
    d1 = primera.get_json()
    assert d1["reenvio"] is False
    assert d1["resumen"]["aplicadas"] == 2

    # El mismo lote, tal cual, como lo haría un cliente que no recibió
    # respuesta.
    segunda = _enviar(cliente, token_colaborador, lote, ops)
    assert segunda.status_code == 200, segunda.get_data(as_text=True)
    d2 = segunda.get_json()
    assert d2["reenvio"] is True
    assert d2["lote_id"] == d1["lote_id"], "Creo un lote nuevo."
    assert d2["resumen"]["aplicadas"] == 2, (
        "El resumen del reenvio no coincide con el de la primera vez. El "
        "cliente tendria que decidir que hacer con la diferencia, que es el "
        "problema que este servicio viene a resolver.")

    # Y en la base hay UNA respuesta por seudónimo, no dos.
    from comun.datos import consultar_uno
    for seudonimo in seudonimos_libres[:2]:
        n = consultar_uno(
            "SELECT count(*) AS n FROM sincronizacion.operacion "
            " WHERE seudonimo_id = %s AND campania_id = %s",
            (seudonimo, CAMPANIA_ABIERTA))["n"]
        assert n == 1, f"{seudonimo} quedo registrado {n} veces."


def test_la_misma_operacion_en_otro_lote_sale_duplicada(
        cliente, token_colaborador, corrida, seudonimos_libres):
    """Un cliente puede repartir la misma operación en dos lotes.

    Pasa de verdad: el cliente reagrupa lo pendiente después de un corte y
    una operación que ya había mandado cae en el lote nuevo.
    """
    clave = f"op-{corrida}-sola"
    op = _operacion(clave, seudonimos_libres[0])

    primera = _enviar(cliente, token_colaborador, f"lote-{corrida}-a", [op])
    assert primera.get_json()["operaciones"][0]["estado"] == "APLICADA"

    segunda = _enviar(cliente, token_colaborador, f"lote-{corrida}-b", [op])
    assert segunda.status_code == 200
    r = segunda.get_json()["operaciones"][0]
    assert r["estado"] == "DUPLICADA"
    assert r["estado_original"] == "APLICADA"
    assert r["reintentable"] is False
    assert r["intentos"] == 2


def test_la_idempotencia_no_es_por_contenido(cliente, token_colaborador,
                                             corrida, seudonimos_libres):
    """Dos personas del mismo turno pueden contestar exactamente lo mismo.

    Con comparación por contenido, la segunda respuesta —legítima— se
    descartaría como duplicada. Es el error que la decisión 1 del servicio
    evita, y sin esta prueba nadie lo notaría: el resultado sería menos
    respuestas, no un error.
    """
    ops = [_operacion(f"op-{corrida}-x", seudonimos_libres[0], valores=dict(VALORES)),
           _operacion(f"op-{corrida}-y", seudonimos_libres[1], valores=dict(VALORES))]
    r = _enviar(cliente, token_colaborador, f"lote-{corrida}", ops)
    assert r.status_code == 200, r.get_data(as_text=True)
    estados = [o["estado"] for o in r.get_json()["operaciones"]]
    assert estados == ["APLICADA", "APLICADA"], (
        f"Contenido identico y seudonimos distintos dieron {estados}. "
        f"Parece que la idempotencia se volvio por contenido.")


# =========================================================================
# El lote no es todo o nada
# =========================================================================

def test_un_renglon_mal_formado_no_tumba_el_lote(cliente, token_colaborador,
                                                 corrida, seudonimos_libres):
    """El cliente que capturó los buenos sin red no puede recuperarlos."""
    ops = [
        _operacion(f"op-{corrida}-ok1", seudonimos_libres[0]),
        {"operacion_cliente_id": f"op-{corrida}-malo", "tipo": "AUTOREPORTE",
         "seudonimo_id": "", "campania_id": CAMPANIA_ABIERTA, "valores": {}},
        _operacion(f"op-{corrida}-ok2", seudonimos_libres[1]),
    ]
    r = _enviar(cliente, token_colaborador, f"lote-{corrida}", ops)
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    assert d["resumen"]["aplicadas"] == 2
    assert d["resumen"]["rechazadas"] == 1
    estados = [o["estado"] for o in d["operaciones"]]
    assert estados == ["APLICADA", "RECHAZADA", "APLICADA"]


def test_un_lote_sin_clave_se_rechaza_entero(cliente, token_colaborador,
                                             seudonimos_libres):
    """Sin clave de lote no hay idempotencia posible, así que aplicarlo
    sería aceptar duplicar en el siguiente reenvío."""
    r = cliente.post("/api/v1/sincronizacion/lotes",
                     headers=_cab(token_colaborador),
                     json={"origen": "MOVIL",
                           "operaciones": [_operacion("x", seudonimos_libres[0])]})
    assert r.status_code == 422
    campos = {d["campo"] for d in r.get_json()["error"]["detalles"]}
    assert "lote_cliente_id" in campos


def test_un_lote_demasiado_grande_se_rechaza(cliente, token_colaborador,
                                             corrida, sincronizacion,
                                             seudonimos_libres):
    """Sin tope, un cliente puede ocupar la conexión y una transacción
    varios minutos. Partir el lote es lo que el cliente ya sabe hacer."""
    tope = sincronizacion.MAXIMO_POR_LOTE
    ops = [_operacion(f"op-{corrida}-{i}", seudonimos_libres[0])
           for i in range(tope + 1)]
    r = _enviar(cliente, token_colaborador, f"lote-{corrida}", ops)
    assert r.status_code == 422
    detalle = " ".join(d["problema"] for d in r.get_json()["error"]["detalles"])
    assert str(tope) in detalle


def test_un_origen_invalido_se_rechaza(cliente, token_colaborador, corrida,
                                       seudonimos_libres):
    r = _enviar(cliente, token_colaborador, f"lote-{corrida}",
                [_operacion(f"op-{corrida}", seudonimos_libres[0])],
                origen="DESDE_MARTE")
    assert r.status_code == 422
    campos = {d["campo"] for d in r.get_json()["error"]["detalles"]}
    assert "origen" in campos


# =========================================================================
# Conflictos: la primera respuesta se conserva
# =========================================================================

def test_un_conflicto_conserva_la_primera_respuesta(cliente, token_colaborador,
                                                    corrida, seudonimos_libres):
    """Último-que-escribe-gana sería grave aquí.

    La primera respuesta puede haber entrado ya en un agregado publicado:
    sobrescribirla cambiaría un número que ya salió, hacia atrás y sin
    rastro.
    """
    seudonimo = seudonimos_libres[0]
    primera = _enviar(cliente, token_colaborador, f"lote-{corrida}-1",
                      [_operacion(f"op-{corrida}-1", seudonimo,
                                  valores={"R-01": 5, "R-02": 5, "R-03": 5,
                                           "R-04": 5, "R-05": 5})])
    assert primera.get_json()["operaciones"][0]["estado"] == "APLICADA"

    # Otra operación (otra clave) para el mismo seudónimo y campaña.
    segunda = _enviar(cliente, token_colaborador, f"lote-{corrida}-2",
                      [_operacion(f"op-{corrida}-2", seudonimo,
                                  valores={"R-01": 1, "R-02": 1, "R-03": 1,
                                           "R-04": 1, "R-05": 1})])
    assert segunda.status_code == 200, segunda.get_data(as_text=True)
    r = segunda.get_json()["operaciones"][0]
    assert r["estado"] == "EN_CONFLICTO"
    assert r["estado_base"] == "YA_RESPONDIDA"
    assert r["reintentable"] is False, (
        "Un conflicto no es reintentable: reenviarlo no lo va a cambiar, y "
        "marcarlo reintentable hace que el cliente lo mande para siempre.")
    assert segunda.get_json()["resumen"]["en_conflicto"] == 1


# =========================================================================
# Lo reintentable y lo que no
# =========================================================================

def test_una_campania_cerrada_si_es_reintentable(cliente, token_colaborador,
                                                 corrida, seudonimos_libres):
    """Es el único caso que vale reintentar: una campaña programada abre
    después, y la respuesta capturada sin red minutos antes es válida en
    cuanto abra."""
    r = _enviar(cliente, token_colaborador, f"lote-{corrida}",
                [_operacion(f"op-{corrida}", seudonimos_libres[0],
                            campania=CAMPANIA_CERRADA)])
    assert r.status_code == 200, r.get_data(as_text=True)
    op = r.get_json()["operaciones"][0]
    assert op["estado"] == "RECHAZADA"
    assert op["estado_base"] == "CAMPANIA_NO_ABIERTA"
    assert op["reintentable"] is True
    assert op["operacion_cliente_id"] in r.get_json()["reintentar"]


def test_un_seudonimo_invalido_no_es_reintentable(cliente, token_colaborador,
                                                  corrida):
    """Volvería a fallar igual. Marcarlo reintentable haría que el cliente
    lo mandara para siempre."""
    r = _enviar(cliente, token_colaborador, f"lote-{corrida}",
                [_operacion(f"op-{corrida}", "SEUD-QUE-NO-EXISTE")])
    assert r.status_code == 200, r.get_data(as_text=True)
    op = r.get_json()["operaciones"][0]
    assert op["estado"] == "RECHAZADA"
    assert op["reintentable"] is False
    assert r.get_json()["reintentar"] == []


def test_la_lista_de_reintentar_solo_trae_lo_reintentable(
        cliente, token_colaborador, corrida, seudonimos_libres):
    """Es la lista que el cliente usa; si trajera de más, reenviaría cosas
    con resultado definitivo para siempre."""
    ops = [
        _operacion(f"op-{corrida}-ok", seudonimos_libres[0]),
        _operacion(f"op-{corrida}-cerrada", seudonimos_libres[1],
                   campania=CAMPANIA_CERRADA),
        _operacion(f"op-{corrida}-malo", "SEUD-QUE-NO-EXISTE"),
    ]
    d = _enviar(cliente, token_colaborador, f"lote-{corrida}", ops).get_json()
    assert d["reintentar"] == [f"op-{corrida}-cerrada"]


# =========================================================================
# El seudónimo, no la persona
# =========================================================================

def test_un_empleado_id_en_el_lote_se_rechaza(cliente, token_colaborador,
                                              corrida, seudonimos_libres):
    """Se rechaza, no se ignora.

    Ignorarlo dejaría al cliente mandándolo para siempre, y la primera vez
    que alguien lo guardara «por si acaso» habría un vínculo
    persona-respuesta en el sistema.
    """
    op = _operacion(f"op-{corrida}", seudonimos_libres[0])
    op["empleado_id"] = "EMP-00042"
    r = _enviar(cliente, token_colaborador, f"lote-{corrida}", [op])
    assert r.status_code == 200, r.get_data(as_text=True)
    resultado = r.get_json()["operaciones"][0]
    assert resultado["estado"] == "RECHAZADA"
    assert "empleado_id" in resultado["mensaje"]
    assert resultado["reintentable"] is False

    # Y no se aplicó: no quedó ninguna operación aplicada para ese
    # seudónimo. Se comprueba aquí y no en `autoreporte.respuesta` porque
    # el rol de la aplicación no puede leer esa tabla, y eso es una
    # garantía del proyecto, no una limitación de la prueba.
    from comun.datos import consultar_uno
    assert not consultar_uno(
        "SELECT 1 AS x FROM sincronizacion.operacion "
        " WHERE seudonimo_id = %s AND campania_id = %s AND estado = 'APLICADA'",
        (seudonimos_libres[0], CAMPANIA_ABIERTA))


@pytest.mark.parametrize("campo", ["correo", "nombre", "curp", "rfc"])
def test_otros_datos_de_persona_tambien_se_rechazan(cliente, token_colaborador,
                                                    corrida, seudonimos_libres,
                                                    campo):
    op = _operacion(f"op-{corrida}-{campo}", seudonimos_libres[0])
    op[campo] = "lo-que-sea"
    r = _enviar(cliente, token_colaborador, f"lote-{corrida}-{campo}", [op])
    assert r.get_json()["operaciones"][0]["estado"] == "RECHAZADA"


# =========================================================================
# Consultar un lote
# =========================================================================

def test_un_lote_desconocido_es_404_y_dice_que_reenviar(cliente,
                                                        token_colaborador):
    """Un 404 aquí es información útil: significa que no llegó."""
    r = cliente.get("/api/v1/sincronizacion/lotes/lote-que-nunca-existio",
                    headers=_cab(token_colaborador))
    assert r.status_code == 404
    error = r.get_json()["error"]
    assert error["codigo"] == "NO_ENCONTRADO"
    assert "reenvialo" in error["mensaje"].lower()


def test_el_lote_se_consulta_por_la_clave_del_cliente(cliente,
                                                      token_colaborador,
                                                      corrida,
                                                      seudonimos_libres):
    """Por la del cliente y no por el identificador interno: si el cliente
    perdió la respuesta, el identificador interno es lo que no tiene."""
    lote = f"lote-{corrida}"
    _enviar(cliente, token_colaborador, lote,
            [_operacion(f"op-{corrida}", seudonimos_libres[0])])
    r = cliente.get(f"/api/v1/sincronizacion/lotes/{lote}",
                    headers=_cab(token_colaborador))
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    assert d["lote_cliente_id"] == lote
    assert len(d["operaciones"]) == 1
    assert d["operaciones"][0]["estado"] == "APLICADA"


# =========================================================================
# El contrato de reintento
# =========================================================================

def test_el_contrato_de_reintento_esta_publicado(cliente, token_colaborador,
                                                 sincronizacion):
    """Las dos aplicaciones cliente implementan el reintento por separado.

    Una regla que viva solo en el servidor se implementa distinto en cada
    una, y la diferencia solo se ve cuando falla la red, que es cuando no
    hay nadie mirando.
    """
    r = cliente.get("/api/v1/sincronizacion/contrato-de-reintento",
                    headers=_cab(token_colaborador))
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    assert d["idempotencia"]["por"] == "operacion_cliente_id"
    assert d["idempotencia"]["no_por"] == "contenido"
    assert d["idempotencia"]["genera"].startswith("El CLIENTE")
    assert d["maximo_por_lote"] == sincronizacion.MAXIMO_POR_LOTE
    # Los cinco estados documentados, porque el cliente decide con ellos.
    assert set(d["estados"]) == {"APLICADA", "DUPLICADA", "EN_CONFLICTO",
                                 "RECHAZADA", "ERROR_TEMPORAL"}
    assert d["conflictos"]["no_es"] == "ultimo-que-escribe-gana"


def test_todo_estado_que_el_servicio_produce_cabe_en_la_base(sincronizacion):
    """La restricción de la tabla es la que de verdad manda.

    Si el servicio produjera un estado que la restricción no admite, el
    INSERT fallaría; y como `_registrar` se traga el error para no tumbar
    el lote, el resultado sería que esa operación no queda registrada y
    pierde su idempotencia **en silencio**. Es el mismo modo de falla que
    ya ocurrió con la bitácora antes de la migración 007.
    """
    from comun.datos import consultar_uno
    definicion = consultar_uno(
        "SELECT pg_get_constraintdef(oid) AS d FROM pg_constraint "
        " WHERE conname = 'ck_operacion_estado'")["d"]

    producidos = {estado for estado, _, _ in sincronizacion.TRADUCCION.values()}
    producidos |= {"DUPLICADA", "ERROR_TEMPORAL"}   # ramas sin traducción
    for estado in producidos:
        assert f"'{estado}'" in definicion, (
            f"El servicio produce '{estado}' y ck_operacion_estado no lo "
            f"admite: el INSERT fallaria y la operacion perderia su "
            f"idempotencia en silencio.")


# =========================================================================
# Permisos
# =========================================================================

def test_enviar_un_lote_exige_el_permiso_de_responder(cliente,
                                                      token_especialista,
                                                      corrida,
                                                      seudonimos_libres):
    """El permiso es el de la persona que contesta, no uno de servicio: la
    aplicación se autentica como quien captura. Un especialista no
    contesta autoreportes de nadie."""
    r = _enviar(cliente, token_especialista, f"lote-{corrida}",
                [_operacion(f"op-{corrida}", seudonimos_libres[0])])
    assert r.status_code == 403
    assert r.get_json()["error"]["codigo"] == "SIN_PERMISO"


def test_sin_token_no_se_sincroniza(cliente, corrida):
    r = cliente.post("/api/v1/sincronizacion/lotes",
                     json={"lote_cliente_id": f"lote-{corrida}",
                           "origen": "MOVIL", "operaciones": []})
    assert r.status_code == 401


def test_los_clientes_insistentes_exigen_permiso_de_operacion(
        cliente, token_colaborador):
    r = cliente.get("/api/v1/sincronizacion/clientes-insistentes",
                    headers=_cab(token_colaborador))
    assert r.status_code == 403
    assert r.get_json()["error"]["codigo"] == "SIN_PERMISO"


def test_los_clientes_insistentes_se_ven_con_permiso(cliente, token_auditor):
    r = cliente.get("/api/v1/sincronizacion/clientes-insistentes",
                    headers=_cab(token_auditor))
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    assert d["umbral_intentos"] == 3
    assert "idempotencia lo absorbe" in d["nota"]


# =========================================================================
# XML, que es lo que manda la aplicación de escritorio
# =========================================================================

def test_un_lote_en_xml_se_procesa(cliente, token_colaborador, corrida,
                                   seudonimos_libres):
    """La aplicación de escritorio del proyecto consume XML exclusivamente.

    Y con un solo elemento el parser devuelve un diccionario en lugar de
    una lista de uno: sin la normalización, un lote de una sola operación
    se leía como vacío.
    """
    cuerpo = f"""<?xml version="1.0" encoding="UTF-8"?>
<lote>
  <lote_cliente_id>lote-{corrida}-xml</lote_cliente_id>
  <origen>ESCRITORIO</origen>
  <operaciones>
    <operacion>
      <operacion_cliente_id>op-{corrida}-xml</operacion_cliente_id>
      <tipo>AUTOREPORTE</tipo>
      <seudonimo_id>{seudonimos_libres[0]}</seudonimo_id>
      <campania_id>{CAMPANIA_ABIERTA}</campania_id>
      <valores>
        <R-01>4</R-01><R-02>3</R-02><R-03>4</R-03>
        <R-04>3</R-04><R-05>5</R-05>
      </valores>
    </operacion>
  </operaciones>
</lote>"""
    r = cliente.post("/api/v1/sincronizacion/lotes",
                     headers=dict(_cab(token_colaborador),
                                  **{"Content-Type": "application/xml"}),
                     data=cuerpo.encode("utf-8"))
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    assert d["resumen"]["recibidas"] == 1, (
        "El lote de una sola operacion se leyo como vacio: es el caso en "
        "que el parser XML devuelve un diccionario y no una lista de uno.")
    assert d["operaciones"][0]["estado"] == "APLICADA"


def test_un_xml_mal_formado_es_400_no_500(cliente, token_colaborador):
    r = cliente.post("/api/v1/sincronizacion/lotes",
                     headers=dict(_cab(token_colaborador),
                                  **{"Content-Type": "application/xml"}),
                     data=b"<lote><origen>MOVIL")
    assert r.status_code == 400, r.get_data(as_text=True)
    assert r.get_json()["error"]["codigo"] == "XML_MAL_FORMADO"


def test_el_formato_que_se_guarda_es_el_que_mando_el_cliente(
        cliente, token_colaborador, corrida, seudonimos_libres):
    """Es lo que permite reproducir un problema de serialización: saber
    cuál de los dos clientes entregó el lote."""
    lote = f"lote-{corrida}-xml2"
    cuerpo = f"""<lote><lote_cliente_id>{lote}</lote_cliente_id>
<origen>ESCRITORIO</origen><operaciones><operacion>
<operacion_cliente_id>op-{corrida}-f</operacion_cliente_id>
<seudonimo_id>{seudonimos_libres[0]}</seudonimo_id>
<campania_id>{CAMPANIA_ABIERTA}</campania_id>
<valores><R-01>4</R-01><R-02>3</R-02><R-03>4</R-03><R-04>3</R-04>
<R-05>5</R-05></valores></operacion></operaciones></lote>"""
    cliente.post("/api/v1/sincronizacion/lotes",
                 headers=dict(_cab(token_colaborador),
                              **{"Content-Type": "application/xml"}),
                 data=cuerpo.encode("utf-8"))
    from comun.datos import consultar_uno
    fila = consultar_uno("SELECT formato, origen FROM sincronizacion.lote "
                         " WHERE lote_cliente_id = %s", (lote,))
    assert fila["formato"] == "XML"
    assert fila["origen"] == "ESCRITORIO"


# =========================================================================
# Contrato
# =========================================================================

def test_el_contrato_cubre_todas_las_rutas(cliente, sincronizacion):
    contrato = cliente.get("/openapi.json").get_json()
    documentadas = set(contrato["paths"])
    reales = {str(r.rule).replace("<lote_cliente_id>", "{lote_cliente_id}")
              for r in sincronizacion.app.url_map.iter_rules()
              if "/sincronizacion" in str(r.rule)}
    faltan = reales - documentadas
    assert not faltan, f"Rutas sin documentar: {faltan}"
