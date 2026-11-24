"""
integration-service — la puerta hacia el sistema corporativo.

LAS DOS PRUEBAS QUE JUSTIFICAN EL ARCHIVO
-----------------------------------------
1. **Un campo de persona se RECHAZA, no se ignora.** Ignorarlo sería lo
   cómodo y no fallaría ninguna prueba escrita a la ligera: el archivo se
   aplicaría, los datos de persona simplemente no se guardarían, y todo
   parecería bien. El problema aparece después: el sistema de origen sigue
   mandándolos, nadie se entera, y el día que alguien «mejore» el
   importador para no desperdiciar datos, ya están llegando.

2. **La integración no crea personas.** Una persona creada por una
   importación no tendría registro de consentimiento, y el consentimiento
   es lo que habilita que su respuesta cuente. Podría empezar a aparecer
   en agregados sin haber aceptado nada.

Y una tercera que protege algo que ya se rompió una vez en este proyecto:
que un árbol cuya plantilla no cuadra se rechace. El control de inferencia
resta la plantilla del padre menos la de las hijas conocidas; con un árbol
que no cuadra, ese resto da cualquier cosa. La semilla lo rompió hasta la
migración 008, y una importación sin esta validación lo rompería otra vez,
esta vez desde fuera.
"""
import os
import uuid

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FUENTE = "FC-RH-CORPORATIVO"
FUENTE_SIN_FINALIDAD = "FC-NOMINA"


@pytest.fixture(scope="module")
def integracion():
    from conftest import _cargar
    modulo = _cargar("integration-service", "svc_integ")
    modulo.app.config["TESTING"] = True
    return modulo


@pytest.fixture
def cliente(integracion):
    return integracion.app.test_client()


@pytest.fixture
def corrida():
    """Sufijo único por corrida.

    Hace falta porque `organizacion.unidad_organizacional` tiene índice
    único sobre (padre, nombre en minúsculas): sin sufijo, la segunda
    corrida de la suite chocaría con las unidades que dejó la primera.
    """
    return uuid.uuid4().hex[:8]


def _cab(token):
    return {"Authorization": f"Bearer {token}"}


def _enviar_estructura(cliente, token, unidades, modo="VALIDAR",
                       fuente=FUENTE):
    return cliente.post("/api/v1/integracion/estructura", headers=_cab(token),
                        json={"fuente_id": fuente, "modo": modo,
                              "unidades": unidades})


def _enviar_identificadores(cliente, token, renglones, modo="VALIDAR",
                            fuente=FUENTE):
    return cliente.post("/api/v1/integracion/identificadores",
                        headers=_cab(token),
                        json={"fuente_id": fuente, "modo": modo,
                              "identificadores": renglones})


def _arbol_valido(corrida):
    """Un subárbol nuevo y coherente: raíz sin padre, hijas que suman.

    Raíz sin padre a propósito. Colgarlo de una unidad existente cambiaría
    la plantilla esperada de ESA unidad y dejaría el árbol general sin
    cuadrar, rompiendo el control de inferencia para el resto de la suite.
    """
    raiz = f"UO-IMP-{corrida}"
    return raiz, [
        {"unidad_organizacional_id": raiz,
         "nombre_unidad": f"Importada {corrida}",
         "unidad_padre_id": None, "tipo": "DEPARTAMENTO",
         "plantilla_declarada": 12},
        {"unidad_organizacional_id": f"{raiz}-A",
         "nombre_unidad": f"Importada {corrida} A",
         "unidad_padre_id": raiz, "tipo": "TURNO",
         "plantilla_declarada": 7},
        {"unidad_organizacional_id": f"{raiz}-B",
         "nombre_unidad": f"Importada {corrida} B",
         "unidad_padre_id": raiz, "tipo": "TURNO",
         "plantilla_declarada": 5},
    ]


def _codigos(respuesta):
    return {h["codigo"] for h in respuesta.get_json()["hallazgos"]}


def _seudonimo_sin_vinculo():
    """Un seudónimo con consentimiento y sin correspondencia ya guardada.

    Dos cosas, las dos deliberadas:

    · Sale de `consentimiento.v_estado_vigente` y NO de
      `consentimiento.seudonimo`: el rol de la aplicación no puede leer esa
      tabla, que es la que vincula el seudónimo con el empleado. La prueba
      se somete a la misma restricción que el servicio; si usara una vía
      privilegiada comprobaría algo que en producción no pasa.

    · Descuenta los que ya tienen vínculo. Un seudónimo no puede
      corresponder a dos identificadores de la misma fuente, así que una
      prueba que tomara «el primero por id» ataría ese seudónimo en la
      primera corrida y chocaría con su propio rastro en la segunda. Pasó:
      estas dos pruebas pasaban solas y fallaban al correr la suite
      completa dos veces.
    """
    from comun.datos import consultar_uno
    fila = consultar_uno(
        "SELECT v.seudonimo_id FROM consentimiento.v_estado_vigente v "
        " WHERE NOT EXISTS (SELECT 1 FROM integracion.identificador_externo e "
        "                    WHERE e.seudonimo_id = v.seudonimo_id "
        "                      AND e.fuente_id = %s) "
        " ORDER BY random() LIMIT 1", (FUENTE,))
    if not fila:
        pytest.skip("No quedan seudonimos sin vinculo para esta fuente.")
    return fila["seudonimo_id"]


# =========================================================================
# 1. Los campos de persona se rechazan, no se ignoran
# =========================================================================

@pytest.mark.parametrize("campo,valor", [
    ("nombre_completo", "Juan Perez"),
    ("correo_institucional", "juan@empresa.com"),
    ("curp", "PEJJ900101HNLRRN01"),
    ("salario_mensual", 24000),
    ("puesto", "Analista"),
    ("fecha_nacimiento", "1990-01-01"),
    ("numero_empleado", "E-0042"),
    ("Teléfono", "8181818181"),
])
def test_un_campo_de_persona_rechaza_el_archivo(cliente, token_admin, corrida,
                                               campo, valor):
    """Rechaza, no ignora. Y la coincidencia es por contenido del nombre.

    `nombre_completo`, `correo_institucional` y `salario_mensual` son los
    nombres que de verdad usa un sistema corporativo: una comparación
    exacta contra «nombre», «correo» y «salario» los dejaría pasar todos.
    `Teléfono` con mayúscula y tilde está aquí porque un filtro que se
    saltea cambiando una tilde no es un filtro.
    """
    raiz, unidades = _arbol_valido(corrida)
    unidades[0][campo] = valor
    r = _enviar_estructura(cliente, token_admin, unidades, modo="APLICAR")
    assert r.status_code == 422, r.get_data(as_text=True)
    d = r.get_json()
    assert d["veredicto"] == "RECHAZADA"
    assert "CAMPO_DE_PERSONA" in _codigos(r)
    # El hallazgo nombra el campo TAL COMO LLEGÓ: quien tiene que arreglar
    # el archivo necesita ver el nombre que escribió.
    hallazgo = next(h for h in d["hallazgos"]
                    if h["codigo"] == "CAMPO_DE_PERSONA")
    assert campo in hallazgo["campo"]
    assert hallazgo["renglon"] == 1


def test_un_campo_de_persona_no_aplica_nada(cliente, token_admin, corrida):
    """La prueba que distingue rechazar de ignorar.

    Si el servicio ignorara el campo, el archivo se aplicaría, la unidad
    quedaría creada y nada fallaría. Esto comprueba que NO se creó.
    """
    raiz, unidades = _arbol_valido(corrida)
    unidades[1]["nombre"] = "Maria Lopez"
    r = _enviar_estructura(cliente, token_admin, unidades, modo="APLICAR")
    assert r.status_code == 422

    from comun.datos import consultar_uno
    assert not consultar_uno(
        "SELECT 1 AS x FROM organizacion.unidad_organizacional "
        " WHERE unidad_organizacional_id = %s", (raiz,)), (
        "Se aplico el archivo a pesar del campo de persona. Si el servicio "
        "lo ignora en lugar de rechazarlo, el origen sigue mandandolo y "
        "nadie se entera.")


def test_la_lista_de_campos_rechazados_esta_publicada(cliente, token_admin):
    """Para que el equipo del sistema corporativo limpie su extracción
    ANTES de mandarla, en lugar de descubrirlo a base de rechazos."""
    r = cliente.get("/api/v1/integracion/campos-rechazados",
                    headers=_cab(token_admin))
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    for esperado in ("nombre", "correo", "curp", "salario", "puesto",
                     "empleado_id", "fecha_nacimiento"):
        assert esperado in d["campos_de_persona_rechazados"], esperado
    assert "contenido del nombre del campo" in d["coincidencia"]
    assert "Crear personas" in d["lo_que_nunca_hace"]


def test_un_campo_no_esperado_es_advertencia_no_error(cliente, token_admin,
                                                      corrida):
    """Si todo fuera error la integración sería inusable; si todo fuera
    advertencia dejaría de proteger."""
    raiz, unidades = _arbol_valido(corrida)
    unidades[0]["centro_de_costos"] = "CC-99"
    r = _enviar_estructura(cliente, token_admin, unidades, modo="VALIDAR")
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    assert d["veredicto"] == "SOLO_VALIDADA"
    assert d["errores"] == 0
    assert d["advertencias"] == 1
    hallazgo = next(h for h in d["hallazgos"]
                    if h["codigo"] == "CAMPO_NO_ESPERADO")
    assert hallazgo["severidad"] == "ADVERTENCIA"
    assert "centro_de_costos" in hallazgo["campo"]


# =========================================================================
# 2. La integración no crea personas
# =========================================================================

def test_un_seudonimo_que_no_existe_es_hallazgo_no_alta(cliente, token_admin,
                                                        corrida):
    """La decisión menos obvia del servicio.

    Una persona creada por una importación no tendría consentimiento, y el
    consentimiento es lo que habilita que su respuesta cuente: podría
    empezar a aparecer en agregados sin haber aceptado nada.
    """
    r = _enviar_identificadores(cliente, token_admin, [
        {"identificador_externo": f"EXT-{corrida}",
         "seudonimo_id": f"SEUD-NO-EXISTE-{corrida}"}], modo="APLICAR")
    assert r.status_code == 422, r.get_data(as_text=True)
    assert "SEUDONIMO_NO_EXISTE" in _codigos(r)
    hallazgo = next(h for h in r.get_json()["hallazgos"]
                    if h["codigo"] == "SEUDONIMO_NO_EXISTE")
    # El detalle explica POR QUÉ, porque es lo que desconcierta a quien
    # integra y lo que evita que pida «que lo cree automáticamente».
    assert "consentimiento" in hallazgo["detalle"].lower()


def test_la_correspondencia_se_aplica_con_un_seudonimo_que_existe(
        cliente, token_admin, corrida):
    from comun.datos import consultar_uno
    seudonimo = _seudonimo_sin_vinculo()
    r = _enviar_identificadores(cliente, token_admin, [
        {"identificador_externo": f"EXT-{corrida}",
         "seudonimo_id": seudonimo}], modo="APLICAR")
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()["veredicto"] == "ACEPTADA"
    assert r.get_json()["aplicados"] == 1

    guardado = consultar_uno(
        "SELECT seudonimo_id FROM integracion.identificador_externo "
        " WHERE fuente_id = %s AND identificador_externo = %s",
        (FUENTE, f"EXT-{corrida}"))
    assert guardado["seudonimo_id"] == seudonimo


def test_dos_identificadores_al_mismo_seudonimo_se_rechazan(cliente,
                                                            token_admin,
                                                            corrida):
    """La misma persona entraría dos veces y contaría doble en cualquier
    conteo."""
    seudonimo = _seudonimo_sin_vinculo()
    primera = _enviar_identificadores(cliente, token_admin, [
        {"identificador_externo": f"EXT-{corrida}-uno",
         "seudonimo_id": seudonimo}], modo="APLICAR")
    assert primera.status_code == 200, primera.get_data(as_text=True)

    segunda = _enviar_identificadores(cliente, token_admin, [
        {"identificador_externo": f"EXT-{corrida}-dos",
         "seudonimo_id": seudonimo}], modo="APLICAR")
    assert segunda.status_code == 409, segunda.get_data(as_text=True)
    assert segunda.get_json()["error"]["codigo"] == "CORRESPONDENCIA_INVALIDA"
    assert "contaria doble" in segunda.get_json()["error"]["mensaje"]


def test_un_campo_de_persona_en_identificadores_se_rechaza(cliente,
                                                           token_admin,
                                                           corrida):
    """Guardar el nombre junto al seudónimo reconstruiría la
    identificación completa, que es lo que la seudonimización evita."""
    r = _enviar_identificadores(cliente, token_admin, [
        {"identificador_externo": f"EXT-{corrida}",
         "seudonimo_id": "SEUD-001",
         "nombre_completo": "Juan Perez"}], modo="APLICAR")
    assert r.status_code == 422
    assert "CAMPO_DE_PERSONA" in _codigos(r)
    assert "identificacion completa" in next(
        h["detalle"] for h in r.get_json()["hallazgos"]
        if h["codigo"] == "CAMPO_DE_PERSONA")


# =========================================================================
# 3. La jerarquía tiene que cuadrar
# =========================================================================

def test_un_arbol_que_no_cuadra_se_rechaza(cliente, token_admin, corrida):
    """Esto ya rompió el control de inferencia una vez en este proyecto.

    La semilla creaba padres con plantilla propia y el control quedó
    neutralizado hasta la migración 008. Una importación sin esta
    validación lo rompería otra vez, y esta vez desde fuera.
    """
    raiz, unidades = _arbol_valido(corrida)
    unidades[0]["plantilla_declarada"] = 30     # las hijas suman 12
    r = _enviar_estructura(cliente, token_admin, unidades, modo="APLICAR")
    assert r.status_code == 422, r.get_data(as_text=True)
    assert "JERARQUIA_NO_CUADRA" in _codigos(r)
    detalle = next(h["detalle"] for h in r.get_json()["hallazgos"]
                   if h["codigo"] == "JERARQUIA_NO_CUADRA")
    # El detalle dice por qué importa: sin eso parece una pulcritud y
    # alguien pide que se relaje.
    assert "umbral k" in detalle
    assert "30" in detalle and "12" in detalle


def test_un_padre_inexistente_se_rechaza(cliente, token_admin, corrida):
    """Aplicarlo dejaría una unidad huérfana, y el alcance de todos los
    perfiles se calcula recorriendo el árbol."""
    r = _enviar_estructura(cliente, token_admin, [
        {"unidad_organizacional_id": f"UO-HUER-{corrida}",
         "nombre_unidad": f"Huerfana {corrida}",
         "unidad_padre_id": "UO-QUE-NO-EXISTE",
         "plantilla_declarada": 3}], modo="APLICAR")
    assert r.status_code == 422
    assert "PADRE_INEXISTENTE" in _codigos(r)


def test_un_ciclo_se_rechaza(cliente, token_admin, corrida):
    """El alcance se calcula con un recorrido recursivo: un ciclo lo deja
    girando."""
    a, b = f"UO-CIC-{corrida}-A", f"UO-CIC-{corrida}-B"
    r = _enviar_estructura(cliente, token_admin, [
        {"unidad_organizacional_id": a, "nombre_unidad": f"Ciclo {corrida} A",
         "unidad_padre_id": b, "plantilla_declarada": 3},
        {"unidad_organizacional_id": b, "nombre_unidad": f"Ciclo {corrida} B",
         "unidad_padre_id": a, "plantilla_declarada": 3}], modo="APLICAR")
    assert r.status_code == 422
    assert "CICLO" in _codigos(r)


def test_una_unidad_que_es_su_propio_padre_da_un_solo_hallazgo(cliente,
                                                               token_admin,
                                                               corrida):
    """Un informe que repite hallazgos hace dudar de la cuenta de errores.

    El primer intento de la función de validación reportaba el auto-padre
    dos veces: una por la comprobación directa y otra por el recorrido
    recursivo, que con un auto-padre genera una cadena infinita.
    """
    uid = f"UO-SELF-{corrida}"
    r = _enviar_estructura(cliente, token_admin, [
        {"unidad_organizacional_id": uid, "nombre_unidad": f"Self {corrida}",
         "unidad_padre_id": uid, "plantilla_declarada": 3}], modo="APLICAR")
    assert r.status_code == 422
    ciclos = [h for h in r.get_json()["hallazgos"] if h["codigo"] == "CICLO"]
    assert len(ciclos) == 1, f"Se reporto {len(ciclos)} veces el mismo ciclo."


def test_un_identificador_repetido_en_el_archivo_se_rechaza(cliente,
                                                            token_admin,
                                                            corrida):
    """Aplicarlo haría que el último gane en silencio, y el archivo
    parecería haberse aplicado entero."""
    uid = f"UO-REP-{corrida}"
    r = _enviar_estructura(cliente, token_admin, [
        {"unidad_organizacional_id": uid, "nombre_unidad": f"Rep {corrida} 1",
         "unidad_padre_id": None, "plantilla_declarada": 0},
        {"unidad_organizacional_id": uid, "nombre_unidad": f"Rep {corrida} 2",
         "unidad_padre_id": None, "plantilla_declarada": 0}], modo="APLICAR")
    assert r.status_code == 422
    assert "IDENTIFICADOR_REPETIDO" in _codigos(r)


@pytest.mark.parametrize("renglon,codigo", [
    ({"unidad_organizacional_id": "x", "nombre_unidad": "X",
      "plantilla_declarada": 0}, "IDENTIFICADOR_INVALIDO"),
    ({"unidad_organizacional_id": "UO-OK-1", "nombre_unidad": "",
      "plantilla_declarada": 0}, "CAMPO_OBLIGATORIO"),
    ({"unidad_organizacional_id": "UO-OK-2", "nombre_unidad": "X",
      "tipo": "LO_QUE_SEA", "plantilla_declarada": 0}, "TIPO_INVALIDO"),
    ({"unidad_organizacional_id": "UO-OK-3", "nombre_unidad": "X",
      "plantilla_declarada": "no-es-numero"}, "NO_ES_ENTERO"),
    ({"unidad_organizacional_id": "UO-OK-4", "nombre_unidad": "X",
      "plantilla_declarada": -1}, "PLANTILLA_NEGATIVA"),
])
def test_cada_validacion_de_renglon_da_su_codigo(cliente, token_admin,
                                                 renglon, codigo):
    """Códigos distintos para problemas distintos.

    Un solo código «VALIDACION» para todo obligaría a leer el texto, y el
    texto cambia; el código es lo que un cliente puede programar.
    """
    r = _enviar_estructura(cliente, token_admin, [renglon], modo="VALIDAR")
    assert r.status_code == 422, r.get_data(as_text=True)
    assert codigo in _codigos(r), r.get_data(as_text=True)


# =========================================================================
# 4. Validar no escribe; aplicar es todo o nada
# =========================================================================

def test_validar_no_escribe_nada(cliente, token_admin, corrida):
    raiz, unidades = _arbol_valido(corrida)
    r = _enviar_estructura(cliente, token_admin, unidades, modo="VALIDAR")
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    assert d["veredicto"] == "SOLO_VALIDADA"
    assert d["aplicados"] == 0
    # El veredicto se distingue de ACEPTADA a propósito: confundirlas haría
    # creer que el árbol ya se actualizó.
    assert "no se escribio" in d["nota"].lower()

    from comun.datos import consultar_uno
    assert not consultar_uno(
        "SELECT 1 AS x FROM organizacion.unidad_organizacional "
        " WHERE unidad_organizacional_id = %s", (raiz,))


def test_aplicar_escribe_el_subarbol_completo(cliente, token_admin, corrida):
    raiz, unidades = _arbol_valido(corrida)
    r = _enviar_estructura(cliente, token_admin, unidades, modo="APLICAR")
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    assert d["veredicto"] == "ACEPTADA"
    assert d["aplicados"] == 3

    from comun.datos import consultar
    filas = consultar(
        "SELECT unidad_organizacional_id, plantilla_declarada "
        "  FROM organizacion.unidad_organizacional "
        " WHERE unidad_organizacional_id LIKE %s ORDER BY 1", (f"{raiz}%",))
    assert len(filas) == 3
    assert {f["plantilla_declarada"] for f in filas} == {12, 7, 5}


def test_el_padre_se_inserta_antes_que_la_hija(cliente, token_admin, corrida):
    """La llave foránea del padre se comprueba al insertar.

    Un archivo que liste la hija antes del padre fallaría aunque el árbol
    sea correcto, y exigirle un orden al sistema de origen es pedirle algo
    que no tiene por qué saber.
    """
    raiz, unidades = _arbol_valido(corrida)
    al_reves = list(reversed(unidades))     # hijas primero
    r = _enviar_estructura(cliente, token_admin, al_reves, modo="APLICAR")
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()["veredicto"] == "ACEPTADA"


def test_la_jerarquia_se_vuelve_a_comprobar_despues_de_aplicar(cliente,
                                                               token_admin,
                                                               corrida):
    """La validación previa mira el archivo; esta mira el árbol que quedó.

    El árbol final incluye unidades que ya estaban y que el archivo no
    tocó, así que un archivo correcto puede dejar un árbol incorrecto.
    """
    _, unidades = _arbol_valido(corrida)
    r = _enviar_estructura(cliente, token_admin, unidades, modo="APLICAR")
    assert r.status_code == 200, r.get_data(as_text=True)
    estado = r.get_json()["jerarquia_tras_aplicar"]
    assert estado["consistente"] is True, estado["unidades_que_no_cuadran"]
    assert "control de inferencia" in estado["por_que_importa"]


def test_aplicar_dos_veces_el_mismo_archivo_no_rompe_nada(cliente,
                                                          token_admin,
                                                          corrida):
    """Un sistema corporativo manda su extracción completa cada noche.

    Si la segunda aplicación fallara por duplicados, la integración
    tendría que llevar la cuenta de lo que ya mandó, que es justo lo que
    no sabe hacer.
    """
    _, unidades = _arbol_valido(corrida)
    primera = _enviar_estructura(cliente, token_admin, unidades,
                                 modo="APLICAR")
    segunda = _enviar_estructura(cliente, token_admin, unidades,
                                 modo="APLICAR")
    assert primera.status_code == 200, primera.get_data(as_text=True)
    assert segunda.status_code == 200, segunda.get_data(as_text=True)
    assert segunda.get_json()["veredicto"] == "ACEPTADA"


# =========================================================================
# Las fuentes
# =========================================================================

def test_una_fuente_no_registrada_no_integra(cliente, token_admin, corrida):
    """Lo normal es aceptar de cualquiera que traiga un token válido, y
    entonces cualquier componente con credenciales de la organización
    puede reescribir el árbol organizacional."""
    _, unidades = _arbol_valido(corrida)
    r = _enviar_estructura(cliente, token_admin, unidades, modo="APLICAR",
                           fuente="FC-INVENTADA")
    assert r.status_code == 403, r.get_data(as_text=True)
    assert r.get_json()["error"]["codigo"] == "FUENTE_NO_REGISTRADA"


def test_una_fuente_sin_esa_finalidad_no_integra(cliente, token_admin,
                                                 corrida):
    """FC-NOMINA está registrada y NO autorizada a propósito.

    Que el permiso sea explícito por fuente evita que una integración
    creada para una cosa se use después para otra sin que nadie lo revise.
    """
    _, unidades = _arbol_valido(corrida)
    r = _enviar_estructura(cliente, token_admin, unidades, modo="APLICAR",
                           fuente=FUENTE_SIN_FINALIDAD)
    assert r.status_code == 403, r.get_data(as_text=True)
    error = r.get_json()["error"]
    assert error["codigo"] == "FUENTE_SIN_ESA_FINALIDAD"
    # El motivo asentado viaja en el error: así quien recibe el rechazo ve
    # la decisión, no solo la negativa.
    assert "finalidad" in error["mensaje"].lower()


def test_las_fuentes_incluyen_las_no_autorizadas_con_su_motivo(cliente,
                                                               token_admin):
    """Una fuente ausente de la lista parece un olvido; una presente con
    el motivo escrito es una decisión que alguien tomó."""
    r = cliente.get("/api/v1/integracion/fuentes", headers=_cab(token_admin))
    assert r.status_code == 200, r.get_data(as_text=True)
    por_id = {f["fuente_id"]: f for f in r.get_json()["fuentes"]}
    assert FUENTE_SIN_FINALIDAD in por_id
    nomina = por_id[FUENTE_SIN_FINALIDAD]
    assert nomina["admite_estructura"] is False
    assert nomina["admite_identificadores"] is False
    assert nomina["motivo"]


# =========================================================================
# El historial
# =========================================================================

def test_una_ingesta_rechazada_tambien_queda_registrada(cliente, token_admin,
                                                        corrida):
    """Las rechazadas son la mitad del valor de tener una puerta: un
    intento de meter campos de persona que no quedara registrado no habría
    existido nunca."""
    raiz, unidades = _arbol_valido(corrida)
    unidades[0]["nombre_completo"] = "Juan Perez"
    r = _enviar_estructura(cliente, token_admin, unidades, modo="APLICAR")
    ingesta_id = r.get_json()["ingesta_id"]

    detalle = cliente.get(f"/api/v1/integracion/ingestas/{ingesta_id}",
                          headers=_cab(token_admin))
    assert detalle.status_code == 200, detalle.get_data(as_text=True)
    d = detalle.get_json()
    assert d["veredicto"] == "RECHAZADA"
    assert d["modo"] == "APLICAR"
    assert d["sello_sha256"] and len(d["sello_sha256"]) == 64
    assert any(h["codigo"] == "CAMPO_DE_PERSONA" for h in d["hallazgos"])


def test_el_historial_lista_las_ingestas(cliente, token_admin, corrida):
    _, unidades = _arbol_valido(corrida)
    _enviar_estructura(cliente, token_admin, unidades, modo="VALIDAR")
    r = cliente.get("/api/v1/integracion/ingestas", headers=_cab(token_admin))
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()["total"] > 0


def test_una_ingesta_inexistente_es_404(cliente, token_admin):
    r = cliente.get("/api/v1/integracion/ingestas/99999999",
                    headers=_cab(token_admin))
    assert r.status_code == 404


# =========================================================================
# XML y permisos
# =========================================================================

def test_la_estructura_se_puede_mandar_en_xml(cliente, token_admin, corrida):
    """La aplicación de escritorio y varios sistemas corporativos entregan
    XML. Y con un solo elemento el parser devuelve un diccionario en vez
    de una lista de uno.

    La raíz tiene que ser `ingesta_estructura`: el nombre es parte del
    contrato desde que hay validación contra XSD, y es lo que distingue
    este archivo del de identificadores. Antes la raíz daba igual, y
    mandar un archivo al endpoint equivocado producía un «faltan
    identificadores» que mandaba a buscar el problema en el archivo.
    """
    cuerpo = f"""<?xml version="1.0" encoding="UTF-8"?>
<ingesta_estructura xmlns="http://nexum.com.mx/bienestar/v1">
  <fuente_id>{FUENTE}</fuente_id>
  <modo>VALIDAR</modo>
  <unidades>
    <unidad>
      <unidad_organizacional_id>UO-XML-{corrida}</unidad_organizacional_id>
      <nombre_unidad>Desde XML {corrida}</nombre_unidad>
      <tipo>AREA</tipo>
      <plantilla_declarada>4</plantilla_declarada>
    </unidad>
  </unidades>
</ingesta_estructura>"""
    r = cliente.post("/api/v1/integracion/estructura",
                     headers=dict(_cab(token_admin),
                                  **{"Content-Type": "application/xml"}),
                     data=cuerpo.encode("utf-8"))
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    assert d["renglones"] == 1, (
        "El archivo de una sola unidad se leyo como vacio: es el caso en "
        "que el parser XML devuelve un diccionario y no una lista de uno.")
    assert d["veredicto"] == "SOLO_VALIDADA"

    from comun.datos import consultar_uno
    assert consultar_uno(
        "SELECT formato FROM integracion.ingesta WHERE ingesta_id = %s",
        (d["ingesta_id"],))["formato"] == "XML"


def test_un_modo_invalido_se_rechaza(cliente, token_admin, corrida):
    _, unidades = _arbol_valido(corrida)
    r = cliente.post("/api/v1/integracion/estructura", headers=_cab(token_admin),
                     json={"fuente_id": FUENTE, "modo": "APLICAR_YA",
                           "unidades": unidades})
    assert r.status_code == 422
    campos = {d["campo"] for d in r.get_json()["error"]["detalles"]}
    assert "modo" in campos


def test_integrar_exige_permiso(cliente, token_colaborador, corrida):
    _, unidades = _arbol_valido(corrida)
    r = _enviar_estructura(cliente, token_colaborador, unidades,
                           modo="VALIDAR")
    assert r.status_code == 403
    assert r.get_json()["error"]["codigo"] == "SIN_PERMISO"


def test_un_especialista_no_reescribe_el_arbol(cliente, token_especialista,
                                               corrida):
    """Modificar el árbol cambia el alcance de todos los perfiles: no es
    una operación de análisis."""
    _, unidades = _arbol_valido(corrida)
    r = _enviar_estructura(cliente, token_especialista, unidades,
                           modo="APLICAR")
    assert r.status_code == 403


def test_sin_token_no_se_integra(cliente, corrida):
    _, unidades = _arbol_valido(corrida)
    r = cliente.post("/api/v1/integracion/estructura",
                     json={"fuente_id": FUENTE, "modo": "VALIDAR",
                           "unidades": unidades})
    assert r.status_code == 401


# =========================================================================
# Contrato
# =========================================================================

def test_el_contrato_cubre_todas_las_rutas(cliente, integracion):
    contrato = cliente.get("/openapi.json").get_json()
    documentadas = set(contrato["paths"])
    reales = {str(r.rule).replace("<int:ingesta_id>", "{ingesta_id}")
              for r in integracion.app.url_map.iter_rules()
              if "/integracion" in str(r.rule)}
    faltan = reales - documentadas
    assert not faltan, f"Rutas sin documentar: {faltan}"


# =========================================================================
# Validación contra el XSD
# =========================================================================
# POR QUÉ HAY DOS DEFENSAS Y NINGUNA SOBRA
# -----------------------------------------
# La lista de campos de persona del servicio es una enumeración, y una
# enumeración siempre deja fuera lo que no previó. El esquema invierte la
# carga: declara lo PERMITIDO, así que rechaza lo no anticipado.
#
# Pero el esquema solo actúa sobre XML y su mensaje es «este elemento no
# se esperaba», que no le dice al equipo del sistema corporativo qué tiene
# que quitar. La lista cubre el JSON y nombra el campo culpable.

def _xml_estructura(corrida, extra="", modo="VALIDAR"):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ingesta_estructura xmlns="http://nexum.com.mx/bienestar/v1">
  <fuente_id>{FUENTE}</fuente_id>
  <modo>{modo}</modo>
  <unidades>
    <unidad>
      <unidad_organizacional_id>UO-XSD-{corrida}</unidad_organizacional_id>
      <nombre_unidad>Desde XSD {corrida}</nombre_unidad>
      <tipo>AREA</tipo>
      <plantilla_declarada>4</plantilla_declarada>{extra}
    </unidad>
  </unidades>
</ingesta_estructura>"""


def _enviar_xml(cliente, token, cuerpo, ruta="/api/v1/integracion/estructura"):
    return cliente.post(ruta,
                        headers=dict(_cab(token),
                                     **{"Content-Type": "application/xml"}),
                        data=cuerpo.encode("utf-8"))


def test_un_xml_valido_pasa_el_esquema(cliente, token_admin, corrida):
    r = _enviar_xml(cliente, token_admin, _xml_estructura(corrida))
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    assert d["validacion_xsd"] == "VALIDADO", (
        "No se valido contra el esquema. La respuesta tiene que decirlo y "
        "no darlo por hecho.")
    assert d["veredicto"] == "SOLO_VALIDADA"


def test_el_esquema_atrapa_un_campo_que_la_lista_negra_no_previo(
        cliente, token_admin, corrida, integracion):
    """La prueba que justifica tener dos defensas.

    `nss_trabajador` NO está en la lista de campos de persona del
    servicio, así que esa lista lo dejaría pasar. El esquema lo rechaza
    igual, porque declara lo permitido en lugar de enumerar lo prohibido.
    """
    assert not any("nss_trabajador" in c
                   for c in integracion.CAMPOS_DE_PERSONA), (
        "Si 'nss_trabajador' entra en la lista negra, esta prueba deja de "
        "comprobar lo que quiere: elige otro campo no previsto.")

    r = _enviar_xml(cliente, token_admin,
                    _xml_estructura(corrida,
                                    "\n      <nss_trabajador>123</nss_trabajador>"))
    assert r.status_code == 422, r.get_data(as_text=True)
    error = r.get_json()["error"]
    assert error["codigo"] == "XSD_INVALIDO"
    assert any("nss_trabajador" in d["problema"] for d in error["detalles"]), (
        error["detalles"])


def test_el_esquema_rechaza_un_campo_de_persona(cliente, token_admin,
                                                corrida):
    r = _enviar_xml(cliente, token_admin,
                    _xml_estructura(corrida,
                                    "\n      <nombre_completo>Juan</nombre_completo>"))
    assert r.status_code == 422
    assert r.get_json()["error"]["codigo"] == "XSD_INVALIDO"


def test_el_esquema_rechaza_un_tipo_que_la_base_no_acepta(cliente,
                                                          token_admin,
                                                          corrida):
    """GERENCIA no está en la restricción de la base.

    Sin el esquema, el servicio lo rechazaba igual —lee los tipos de la
    propia restricción— pero más tarde. Rechazarlo en el esquema significa
    que el equipo corporativo puede verlo con su propio validador, sin
    mandar nada.
    """
    cuerpo = _xml_estructura(corrida).replace("<tipo>AREA</tipo>",
                                              "<tipo>GERENCIA</tipo>")
    r = _enviar_xml(cliente, token_admin, cuerpo)
    assert r.status_code == 422
    assert r.get_json()["error"]["codigo"] == "XSD_INVALIDO"


def test_el_archivo_al_endpoint_equivocado_se_detecta(cliente, token_admin,
                                                      corrida):
    """Mandar la estructura al endpoint de identificadores, o al revés.

    Sin la comprobación de raíz, el error sería «faltan identificadores»,
    que manda a buscar el problema en el archivo y no en la URL.
    """
    r = _enviar_xml(cliente, token_admin, _xml_estructura(corrida),
                    ruta="/api/v1/integracion/identificadores")
    assert r.status_code == 422, r.get_data(as_text=True)
    error = r.get_json()["error"]
    assert error["codigo"] == "RAIZ_INESPERADA"
    assert "al reves" in error["mensaje"]


def test_un_xml_mal_formado_es_400_no_500(cliente, token_admin):
    r = _enviar_xml(cliente, token_admin,
                    "<ingesta_estructura><fuente_id>sin cerrar")
    assert r.status_code == 400, r.get_data(as_text=True)
    assert r.get_json()["error"]["codigo"] == "XML_MAL_FORMADO"


def test_en_json_la_validacion_no_aplica_y_se_dice(cliente, token_admin,
                                                   corrida):
    """NO_APLICA no es NO_DISPONIBLE ni VALIDADO.

    Los tres significan cosas distintas y confundirlos haría creer que un
    cuerpo JSON pasó por un validador que solo mira XML.
    """
    _, unidades = _arbol_valido(corrida)
    d = _enviar_estructura(cliente, token_admin, unidades,
                           modo="VALIDAR").get_json()
    assert d["validacion_xsd"] == "NO_APLICA"


def test_el_esquema_se_publica_y_es_el_mismo_que_se_usa(cliente, token_admin):
    """Si se mandara por correo, las dos copias se separarían.

    Y entonces un archivo correcto según la copia vieja se rechaza sin
    explicación entendible.
    """
    r = cliente.get("/api/v1/integracion/esquema.xsd",
                    headers=_cab(token_admin))
    assert r.status_code == 200, r.get_data(as_text=True)
    assert "xml" in r.headers["Content-Type"]
    publicado = r.get_data(as_text=True)
    assert "ingesta_estructura" in publicado
    assert "ingesta_identificadores" in publicado

    with open(os.path.join(RAIZ, "contratos", "xml", "integracion.xsd"),
              encoding="utf-8") as f:
        assert publicado == f.read(), (
            "El esquema publicado no es el mismo archivo contra el que se "
            "valida.")


def test_el_esquema_exige_token(cliente):
    assert cliente.get("/api/v1/integracion/esquema.xsd").status_code == 401


def test_el_xsd_declara_los_tipos_que_acepta_la_base():
    """Un XSD no puede consultar la base, así que la lista está repetida.

    Esta prueba es lo que impide que las dos copias se separen. Si alguien
    agrega un tipo de unidad en la base y no aquí, un archivo correcto se
    rechazaría en el esquema sin que nada lo explique.
    """
    from comun.datos import consultar_uno
    import re as _re
    definicion = consultar_uno(
        "SELECT pg_get_constraintdef(oid) AS d FROM pg_constraint "
        " WHERE conname = 'unidad_organizacional_tipo_check'")["d"]
    en_la_base = set(_re.findall(r"'([A-Z_]+)'::", definicion))

    with open(os.path.join(RAIZ, "contratos", "xml", "integracion.xsd"),
              encoding="utf-8") as f:
        xsd = f.read()
    bloque = xsd[xsd.index('name="TipoUnidad"'):]
    bloque = bloque[:bloque.index("</xs:simpleType>")]
    en_el_xsd = set(_re.findall(r'xs:enumeration value="([A-Z_]+)"', bloque))

    assert en_el_xsd == en_la_base, (
        f"El XSD y la restriccion de la base no coinciden.\\n"
        f"  solo en el XSD: {sorted(en_el_xsd - en_la_base)}\\n"
        f"  solo en la base: {sorted(en_la_base - en_el_xsd)}")
