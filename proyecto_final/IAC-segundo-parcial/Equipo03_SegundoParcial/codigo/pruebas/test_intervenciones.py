"""
interventions-service — planes, seguimiento y evaluación.

LO QUE MÁS IMPORTA PROBAR AQUÍ
------------------------------
Casi todo lo valioso de este servicio es negativo —lo que se NIEGA a
hacer—, que es justo lo que una prueba descuidada no cubre:

  · que no se pueda saltar un paso del ciclo de aprobación;
  · que un plan terminado no se reabra;
  · que un valor suprimido NO se trate como cero al evaluar;
  · que la evaluación no gaste presupuesto de épsilon;
  · que el alcance del perfil se respete también cuando el cliente no
    filtra por unidad.

La tercera es la más cara si falla. Si el antes o el después vino
suprimido y el servicio lo tomara como cero, produciría una «mejora» o un
«deterioro» inventados, y sobre ese número se decidiría si la intervención
funcionó.
"""
import os

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def intervenciones():
    """El servicio en memoria, con PostgreSQL real detrás.

    Se carga con `_cargar` de conftest y NO agregando la carpeta del
    servicio a sys.path: cada servicio tiene su propio `app.py` y su propio
    `contrato.py`, así que dejar una de esas carpetas en la ruta de
    búsqueda hace que el siguiente `import app` de la suite resuelva al
    servicio equivocado. Ya pasó una vez.
    """
    from conftest import _cargar
    modulo = _cargar("interventions-service", "svc_interv")
    modulo.app.config["TESTING"] = True
    return modulo


@pytest.fixture
def cliente(intervenciones):
    return intervenciones.app.test_client()


def _cab(token):
    return {"Authorization": f"Bearer {token}"}


def _crear(cliente, token, unidad="UO-CC-TURNO-B",
           tipo="REDISTRIBUCION_CARGA"):
    r = cliente.post("/api/v1/intervenciones", headers=_cab(token),
                     json={"unidad_organizacional_id": unidad,
                           "tipo_intervencion": tipo,
                           "justificacion": "La carga percibida viene por "
                                            "debajo del umbral tres campanias "
                                            "seguidas.",
                           "resultado_esperado": "Recuperar el nivel de carga "
                                                 "percibida de la campania "
                                                 "CAMP-2026-S1."})
    assert r.status_code == 201, r.get_data(as_text=True)
    return r.get_json()["intervencion_id"]


@pytest.fixture
def plan_nuevo(cliente, token_especialista):
    return _crear(cliente, token_especialista)


# =========================================================================
# El catálogo y la garantía del modelo
# =========================================================================

def test_todos_los_tipos_son_organizacionales(cliente, token_especialista):
    """La garantía G1, vista desde el catálogo.

    No existe un tipo de intervención cuyo ámbito sea una persona. La
    ausencia ES la garantía.
    """
    r = cliente.get("/api/v1/intervenciones/tipos",
                    headers=_cab(token_especialista))
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    assert d["total"] > 0
    for tipo in d["tipos"]:
        assert (tipo.get("ambito") or "").upper() == "ORGANIZACIONAL", tipo


def test_el_esquema_no_admite_un_objetivo_individual():
    """Se comprueba contra el catálogo del sistema, no contra el código.

    Una prueba que mirara el código solo diría que hoy ningún endpoint
    guarda un empleado. Esta dice que no hay DÓNDE guardarlo, que es la
    forma fuerte de la garantía: un endpoint futuro tampoco podría.
    """
    from comun.datos import consultar
    columnas = consultar(
        "SELECT table_name, column_name FROM information_schema.columns "
        " WHERE table_schema = 'intervencion' "
        "   AND (column_name ILIKE '%%empleado%%' "
        "        OR column_name ILIKE '%%seudonimo%%')")
    assert not columnas, (
        f"El esquema intervencion admite un objetivo individual: "
        f"{[dict(c) for c in columnas]}. Eso rompe la garantia G1.")


# =========================================================================
# Crear un plan
# =========================================================================

def test_no_se_puede_crear_un_plan_sin_justificacion(cliente,
                                                     token_especialista):
    """Intervenir sin dejar dicho por qué es lo que vuelve esto presión."""
    r = cliente.post("/api/v1/intervenciones", headers=_cab(token_especialista),
                     json={"unidad_organizacional_id": "UO-CC-TURNO-B",
                           "tipo_intervencion": "REDISTRIBUCION_CARGA",
                           "justificacion": "porque si",
                           "resultado_esperado": "que mejore"})
    assert r.status_code == 422
    campos = {d["campo"] for d in r.get_json()["error"]["detalles"]}
    assert campos == {"justificacion", "resultado_esperado"}


def test_un_tipo_que_no_esta_en_el_catalogo_se_rechaza(cliente,
                                                       token_especialista):
    r = cliente.post("/api/v1/intervenciones", headers=_cab(token_especialista),
                     json={"unidad_organizacional_id": "UO-CC-TURNO-B",
                           "tipo_intervencion": "DESPEDIR_AL_EQUIPO",
                           "justificacion": "x" * 25,
                           "resultado_esperado": "y" * 25})
    assert r.status_code == 422
    assert r.get_json()["error"]["codigo"] == "TIPO_NO_EXISTE"


def test_una_unidad_inexistente_es_422_no_500(cliente, token_especialista):
    r = cliente.post("/api/v1/intervenciones", headers=_cab(token_especialista),
                     json={"unidad_organizacional_id": "UO-QUE-NO-EXISTE",
                           "tipo_intervencion": "REDISTRIBUCION_CARGA",
                           "justificacion": "x" * 25,
                           "resultado_esperado": "y" * 25})
    assert r.status_code == 422
    assert r.get_json()["error"]["codigo"] == "UNIDAD_NO_EXISTE"


def test_un_plan_nace_en_propuesta(cliente, token_especialista, plan_nuevo):
    r = cliente.get(f"/api/v1/intervenciones/{plan_nuevo}",
                    headers=_cab(token_especialista))
    assert r.status_code == 200
    d = r.get_json()
    assert d["plan"]["estado"] == "PROPUESTA"
    # El cliente no tiene que conocer la máquina de estados ni adivinarla.
    assert set(d["transiciones_posibles"]) == {"APROBADA", "CANCELADA"}


# =========================================================================
# El ciclo de vida
# =========================================================================

def test_no_se_puede_saltar_un_paso_del_ciclo(cliente, token_especialista,
                                              plan_nuevo):
    """De PROPUESTA a FINALIZADA sin aprobar ni ejecutar: 409."""
    r = cliente.patch(f"/api/v1/intervenciones/{plan_nuevo}/estado",
                      headers=_cab(token_especialista),
                      json={"estado": "FINALIZADA"})
    assert r.status_code == 409
    error = r.get_json()["error"]
    assert error["codigo"] == "TRANSICION_INVALIDA"
    # El error dice cuáles SÍ se pueden: sin eso, el cliente adivina.
    campos = {d["campo"]: d["problema"] for d in error["detalles"]}
    assert campos["estado_actual"] == "PROPUESTA"
    assert "APROBADA" in campos["permitidos"]


def test_un_plan_finalizado_no_se_reabre(cliente, token_especialista,
                                         plan_nuevo):
    """Reabrirlo borraría la historia de lo que ya se intentó."""
    for destino in ("APROBADA", "EN_EJECUCION", "FINALIZADA"):
        r = cliente.patch(f"/api/v1/intervenciones/{plan_nuevo}/estado",
                          headers=_cab(token_especialista),
                          json={"estado": destino})
        assert r.status_code == 200, r.get_data(as_text=True)

    r = cliente.patch(f"/api/v1/intervenciones/{plan_nuevo}/estado",
                      headers=_cab(token_especialista),
                      json={"estado": "EN_EJECUCION"})
    assert r.status_code == 409
    assert r.get_json()["error"]["codigo"] == "TRANSICION_INVALIDA"
    # Y el mensaje dice que es un estado final, no una lista vacía a secas.
    assert "final" in r.get_json()["error"]["mensaje"].lower()


def test_cancelar_se_puede_desde_un_estado_vivo(cliente, token_especialista,
                                                plan_nuevo):
    r = cliente.patch(f"/api/v1/intervenciones/{plan_nuevo}/estado",
                      headers=_cab(token_especialista),
                      json={"estado": "CANCELADA"})
    assert r.status_code == 200
    d = r.get_json()
    assert d["estado"] == "CANCELADA"
    assert d["estado_anterior"] == "PROPUESTA"
    assert d["transiciones_posibles"] == []


def test_un_estado_que_no_existe_se_rechaza(cliente, token_especialista,
                                            plan_nuevo):
    r = cliente.patch(f"/api/v1/intervenciones/{plan_nuevo}/estado",
                      headers=_cab(token_especialista),
                      json={"estado": "APROBADISIMA"})
    assert r.status_code == 409
    assert r.get_json()["error"]["codigo"] == "TRANSICION_INVALIDA"


# =========================================================================
# Seguimiento
# =========================================================================

def test_no_se_registra_avance_de_algo_que_no_empezo(cliente,
                                                     token_especialista,
                                                     plan_nuevo):
    r = cliente.post(f"/api/v1/intervenciones/{plan_nuevo}/seguimiento",
                     headers=_cab(token_especialista),
                     json={"estado_reportado": "EN_TIEMPO",
                           "avance_nota": "Se reviso la carga del turno."})
    assert r.status_code == 409
    assert r.get_json()["error"]["codigo"] == "ESTADO_INCOMPATIBLE"


def test_el_avance_se_registra_sobre_un_plan_aprobado(cliente,
                                                      token_especialista,
                                                      plan_nuevo):
    cliente.patch(f"/api/v1/intervenciones/{plan_nuevo}/estado",
                  headers=_cab(token_especialista), json={"estado": "APROBADA"})
    r = cliente.post(f"/api/v1/intervenciones/{plan_nuevo}/seguimiento",
                     headers=_cab(token_especialista),
                     json={"estado_reportado": "EN_TIEMPO",
                           "avance_nota": "Se reviso la carga del turno con "
                                          "el jefe de area."})
    assert r.status_code == 201, r.get_data(as_text=True)

    d = cliente.get(f"/api/v1/intervenciones/{plan_nuevo}",
                    headers=_cab(token_especialista)).get_json()
    assert len(d["seguimiento"]) == 1
    assert d["seguimiento"][0]["estado_reportado"] == "EN_TIEMPO"


def test_una_nota_de_avance_demasiado_corta_se_rechaza(cliente,
                                                       token_especialista,
                                                       plan_nuevo):
    cliente.patch(f"/api/v1/intervenciones/{plan_nuevo}/estado",
                  headers=_cab(token_especialista), json={"estado": "APROBADA"})
    r = cliente.post(f"/api/v1/intervenciones/{plan_nuevo}/seguimiento",
                     headers=_cab(token_especialista),
                     json={"estado_reportado": "EN_TIEMPO", "avance_nota": "ok"})
    assert r.status_code == 422
    campos = {d["campo"] for d in r.get_json()["error"]["detalles"]}
    assert "avance_nota" in campos


# =========================================================================
# Evaluación: las pruebas que más importan
# =========================================================================

def _valores_falsos(intervenciones, monkeypatch, por_campania):
    """Sustituye SOLO la lectura del tablero publicado.

    Lo demás —el plan, el alcance, la escritura— sigue yendo a PostgreSQL
    de verdad. Si se sustituyera `consultar_uno` completo, la prueba
    dejaría de tocar la base y no probaría la ruta real.

    Hace falta porque los valores agregados de la base llevan ruido de
    Laplace: no se puede fijar en la base un «antes» y un «después»
    exactos, y sin valores exactos no se puede comprobar el signo ni el
    caso suprimido.
    """
    real = intervenciones.consultar_uno

    def envoltura(sql, params=None):
        if "v_tablero_unidad" in sql:
            return por_campania.get(params[1])
        return real(sql, params)

    monkeypatch.setattr(intervenciones, "consultar_uno", envoltura)


def test_un_valor_suprimido_no_se_toma_como_cero(cliente, token_especialista,
                                                 plan_nuevo, monkeypatch,
                                                 intervenciones):
    """Si lo tomara como cero, inventaría una mejora o un deterioro.

    Y sobre ese número se decidiría si la intervención funcionó.
    """
    _valores_falsos(intervenciones, monkeypatch, {
        "CAMP-2026-S1": {"valor_protegido": 3.5,
                         "estado_publicacion": "PUBLICADO"},
        # La segunda vino suprimida: no hay valor que comparar.
        "CAMP-2026-S4": {"valor_protegido": None,
                         "estado_publicacion": "GRUPO_INSUFICIENTE"},
    })

    r = cliente.post(f"/api/v1/intervenciones/{plan_nuevo}/evaluacion",
                     headers=_cab(token_especialista),
                     json={"campania_antes": "CAMP-2026-S1",
                           "campania_despues": "CAMP-2026-S4"})
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    assert d["conclusion"] == "SIN_DATOS_SUFICIENTES"
    # Tiene que decir CUÁL de las dos falta, y por qué.
    assert len(d["sin_valor_en"]) == 1
    assert "CAMP-2026-S4" in d["sin_valor_en"][0]
    assert "GRUPO_INSUFICIENTE" in d["sin_valor_en"][0]
    assert "no se toma como cero" in d["nota"].lower()
    # Y no se inventa una variación.
    assert "variacion" not in d


def test_sin_datos_suficientes_no_se_guarda(cliente, token_especialista,
                                            plan_nuevo, monkeypatch,
                                            intervenciones):
    """No es una conclusión: es la ausencia de una.

    Guardarla dejaría una fila de evaluación en el plan y, como solo se
    admite una por plan, el plan quedaría cerrado sin haberse evaluado
    nunca.
    """
    _valores_falsos(intervenciones, monkeypatch, {
        "CAMP-2026-S1": {"valor_protegido": None,
                         "estado_publicacion": "GRUPO_INSUFICIENTE"},
        "CAMP-2026-S4": {"valor_protegido": None,
                         "estado_publicacion": "GRUPO_INSUFICIENTE"},
    })
    cliente.post(f"/api/v1/intervenciones/{plan_nuevo}/evaluacion",
                 headers=_cab(token_especialista),
                 json={"campania_antes": "CAMP-2026-S1",
                       "campania_despues": "CAMP-2026-S4"})

    from comun.datos import consultar
    filas = consultar("SELECT 1 AS x FROM intervencion.evaluacion "
                      " WHERE intervencion_id = %s", (plan_nuevo,))
    assert not filas, ("SIN_DATOS_SUFICIENTES se guardo. El plan queda "
                       "cerrado sin haberse evaluado nunca, porque solo se "
                       "admite una evaluacion por plan.")


def test_la_evaluacion_no_gasta_epsilon(cliente, token_especialista, plan_nuevo,
                                        monkeypatch, intervenciones):
    _valores_falsos(intervenciones, monkeypatch, {
        "CAMP-2026-S1": {"valor_protegido": 3.0,
                         "estado_publicacion": "PUBLICADO"},
        "CAMP-2026-S4": {"valor_protegido": 3.6,
                         "estado_publicacion": "PUBLICADO"},
    })
    r = cliente.post(f"/api/v1/intervenciones/{plan_nuevo}/evaluacion",
                     headers=_cab(token_especialista),
                     json={"campania_antes": "CAMP-2026-S1",
                           "campania_despues": "CAMP-2026-S4"})
    assert r.status_code == 201, r.get_data(as_text=True)
    d = r.get_json()
    assert d["epsilon_consumido"] == 0.0
    assert d["conclusion"] == "MEJORA"
    assert d["variacion"] == pytest.approx(0.6, abs=1e-6)
    # La nota deja dicho que esto NO prueba causalidad.
    assert "causalidad" in d["nota_metodologica"].lower()


def test_una_bajada_es_deterioro_no_mejora(cliente, token_especialista,
                                           plan_nuevo, monkeypatch,
                                           intervenciones):
    """El signo importa: en este instrumento, más alto es mejor.

    Si estuviera invertido, el servicio reportaría como éxito justo las
    unidades que empeoraron.
    """
    _valores_falsos(intervenciones, monkeypatch, {
        "CAMP-2026-S1": {"valor_protegido": 3.8,
                         "estado_publicacion": "PUBLICADO"},
        "CAMP-2026-S4": {"valor_protegido": 3.1,
                         "estado_publicacion": "PUBLICADO"},
    })
    r = cliente.post(f"/api/v1/intervenciones/{plan_nuevo}/evaluacion",
                     headers=_cab(token_especialista),
                     json={"campania_antes": "CAMP-2026-S1",
                           "campania_despues": "CAMP-2026-S4"})
    assert r.status_code == 201, r.get_data(as_text=True)
    assert r.get_json()["conclusion"] == "DETERIORO"
    assert r.get_json()["variacion"] < 0


def test_no_se_evalua_dos_veces_el_mismo_plan(cliente, token_especialista,
                                              plan_nuevo, monkeypatch,
                                              intervenciones):
    """Repetir con otro par de campañas sería ir de compras por un resultado.

    Y sin la comprobación, la segunda evaluación reventaba contra la
    restricción UNIQUE de la tabla: salía 500 con el texto de PostgreSQL
    asomando en la respuesta.
    """
    _valores_falsos(intervenciones, monkeypatch, {
        "CAMP-2026-S1": {"valor_protegido": 3.0,
                         "estado_publicacion": "PUBLICADO"},
        "CAMP-2026-S2": {"valor_protegido": 2.5,
                         "estado_publicacion": "PUBLICADO"},
        "CAMP-2026-S4": {"valor_protegido": 3.6,
                         "estado_publicacion": "PUBLICADO"},
    })
    primera = cliente.post(f"/api/v1/intervenciones/{plan_nuevo}/evaluacion",
                           headers=_cab(token_especialista),
                           json={"campania_antes": "CAMP-2026-S1",
                                 "campania_despues": "CAMP-2026-S4"})
    assert primera.status_code == 201

    # Segundo intento, con el par que deja mejor a la intervención.
    segunda = cliente.post(f"/api/v1/intervenciones/{plan_nuevo}/evaluacion",
                           headers=_cab(token_especialista),
                           json={"campania_antes": "CAMP-2026-S2",
                                 "campania_despues": "CAMP-2026-S4"})
    assert segunda.status_code == 409, segunda.get_data(as_text=True)
    assert segunda.get_json()["error"]["codigo"] == "EVALUACION_YA_EXISTE"
    # Y no se filtra el error de la base.
    assert "psycopg2" not in segunda.get_data(as_text=True)


def test_faltar_una_campania_es_400_no_500(cliente, token_especialista,
                                           plan_nuevo):
    r = cliente.post(f"/api/v1/intervenciones/{plan_nuevo}/evaluacion",
                     headers=_cab(token_especialista),
                     json={"campania_antes": "CAMP-2026-S1"})
    assert r.status_code == 400
    assert r.get_json()["error"]["codigo"] == "CAMPOS_OBLIGATORIOS"


def test_la_evaluacion_nunca_llama_a_la_funcion_que_gasta_epsilon():
    """Si la llamara, evaluar una intervención gastaría privacidad.

    Y al agotar el presupuesto dejaría a la campaña sin poder publicar.
    """
    ruta = os.path.join(RAIZ, "apps", "microservicios",
                        "interventions-service", "app.py")
    with open(ruta, encoding="utf-8") as f:
        fuente = f.read()
    assert "fn_calcular_agregado_protegido" not in fuente
    assert "v_tablero_unidad" in fuente, (
        "Tiene que leer de la vista de resultados YA publicados.")


# =========================================================================
# Alcance y permisos
# =========================================================================

def test_un_colaborador_no_propone_intervenciones(cliente, token_colaborador):
    r = cliente.post("/api/v1/intervenciones", headers=_cab(token_colaborador),
                     json={"unidad_organizacional_id": "UO-CC-TURNO-B",
                           "tipo_intervencion": "REDISTRIBUCION_CARGA",
                           "justificacion": "x" * 25,
                           "resultado_esperado": "y" * 25})
    assert r.status_code == 403
    assert r.get_json()["error"]["codigo"] == "SIN_PERMISO"


def test_un_lider_no_ve_un_plan_fuera_de_su_alcance(cliente,
                                                    token_especialista,
                                                    token_lider):
    """El alcance sale del perfil, no del parámetro de la petición.

    Si saliera del parámetro, bastaría cambiar la URL para ver los planes
    de otra área. El líder de UO-CC-TURNO-B tiene permiso de consulta, así
    que lo que lo detiene aquí es el alcance y nada más.
    """
    ajeno = _crear(cliente, token_especialista, unidad="UO-LOG-TURNO-A")
    propio = _crear(cliente, token_especialista, unidad="UO-CC-TURNO-B")

    r = cliente.get(f"/api/v1/intervenciones/{ajeno}",
                    headers=_cab(token_lider))
    assert r.status_code == 403, r.get_data(as_text=True)
    assert r.get_json()["error"]["codigo"] == "FUERA_DE_ALCANCE"

    # Y sí ve el de su propia unidad: la restricción acota, no bloquea.
    r = cliente.get(f"/api/v1/intervenciones/{propio}",
                    headers=_cab(token_lider))
    assert r.status_code == 200, r.get_data(as_text=True)


def test_el_listado_tambien_acota_por_alcance(cliente, token_especialista,
                                              token_lider):
    """Sin esto, un líder que no filtre por unidad vería el árbol completo.

    Es el descuido clásico: se valida el alcance cuando el cliente pide una
    unidad, y se olvida el caso en que no pide ninguna.
    """
    _crear(cliente, token_especialista, unidad="UO-LOG-TURNO-A")
    r = cliente.get("/api/v1/intervenciones?tamano=100",
                    headers=_cab(token_lider))
    assert r.status_code == 200, r.get_data(as_text=True)
    unidades = {p["unidad_organizacional_id"] for p in r.get_json()["planes"]}
    assert unidades <= {"UO-CC-TURNO-B"}, (
        f"El listado devolvio unidades fuera del alcance del lider: "
        f"{unidades - {'UO-CC-TURNO-B'}}")


def test_un_plan_inexistente_es_404(cliente, token_especialista):
    r = cliente.get("/api/v1/intervenciones/99999999",
                    headers=_cab(token_especialista))
    assert r.status_code == 404
    assert r.get_json()["error"]["codigo"] == "NO_ENCONTRADO"


# =========================================================================
# Contrato y sonda de salud
# =========================================================================

def test_el_contrato_cubre_todas_las_rutas(cliente, intervenciones):
    contrato = cliente.get("/openapi.json").get_json()
    documentadas = set(contrato["paths"])
    reales = {str(r.rule).replace("<int:intervencion_id>", "{intervencion_id}")
              for r in intervenciones.app.url_map.iter_rules()
              if "/intervenciones" in str(r.rule)}
    faltan = reales - documentadas
    assert not faltan, f"Rutas sin documentar: {faltan}"


def test_la_sonda_de_salud_declara_sus_dependencias(cliente):
    """Las dos son esenciales aquí, y eso tiene que estar declarado.

    PostgreSQL guarda los planes y Redis sostiene la lista de revocación
    de tokens: sin ninguno de los dos el servicio no puede atender, así
    que ninguno es opcional.
    """
    r = cliente.get("/health/ready")
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    assert d["estado"] == "listo"
    assert set(d["dependencias"]) >= {"postgresql", "redis"}
    for nombre in ("postgresql", "redis"):
        assert d["dependencias"][nombre]["esencial"] is True, nombre


# =========================================================================
# El rastro del ciclo, que es la razón de que las transiciones existan
# =========================================================================

def test_cada_paso_del_ciclo_queda_en_la_bitacora(cliente, token_especialista,
                                                  plan_nuevo):
    """Sin esto, las transiciones declaradas no sirven para nada.

    El ciclo de aprobación está declarado para poder auditarlo: saber
    quién movió un plan y cuándo. Si el registro no entra, la máquina de
    estados solo impide saltos y no deja constancia de los pasos que sí se
    dieron, que es la mitad del valor.

    Esta prueba existe porque eso estaba roto y nadie lo veía. El servicio
    registraba el cambio de estado con el código
    `INTERVENCION_SEGUIMIENTO`, que existe como PERMISO pero no como
    acción de bitácora, así que el INSERT fallaba por llave foránea y el
    try se lo tragaba. Ni un cambio de estado ni un avance quedaban
    registrados.

    Y la prueba que ya existía para este modo de falla no lo atrapó:
    buscaba el código en el texto de las migraciones, y la cadena aparecía
    ahí —como permiso—. Ahora comprueba contra los INSERT a
    `auditoria.tipo_accion`.
    """
    from comun.datos import consultar_uno

    def cuantas(accion):
        return consultar_uno(
            "SELECT count(*) AS n FROM auditoria.bitacora "
            " WHERE accion = %s AND recurso_id = %s",
            (accion, str(plan_nuevo)))["n"]

    assert cuantas("INTERVENCION_PROPUESTA") == 1, (
        "Ni la propuesta quedo registrada.")

    cliente.patch(f"/api/v1/intervenciones/{plan_nuevo}/estado",
                  headers=_cab(token_especialista), json={"estado": "APROBADA"})
    assert cuantas("INTERVENCION_APROBADA") == 1

    cliente.patch(f"/api/v1/intervenciones/{plan_nuevo}/estado",
                  headers=_cab(token_especialista),
                  json={"estado": "EN_EJECUCION"})
    assert cuantas("INTERVENCION_ESTADO_CAMBIADO") == 1, (
        "El paso a EN_EJECUCION no quedo registrado. Es el modo de falla "
        "silencioso: el INSERT va en un try para no tumbar la peticion, asi "
        "que un codigo de accion no declarado se pierde sin ruido.")

    cliente.post(f"/api/v1/intervenciones/{plan_nuevo}/seguimiento",
                 headers=_cab(token_especialista),
                 json={"estado_reportado": "EN_TIEMPO",
                       "avance_nota": "Se reviso la carga con el jefe de "
                                      "area."})
    assert cuantas("INTERVENCION_AVANCE") == 1


def test_aprobar_y_avanzar_no_comparten_codigo_de_bitacora(cliente,
                                                           token_especialista,
                                                           plan_nuevo):
    """Son dos hechos distintos del ciclo y tienen que distinguirse.

    Con un solo código, reconstruir cuándo se movió un plan exige leer las
    notas de avance y adivinar.
    """
    for destino in ("APROBADA", "EN_EJECUCION"):
        cliente.patch(f"/api/v1/intervenciones/{plan_nuevo}/estado",
                      headers=_cab(token_especialista),
                      json={"estado": destino})
    cliente.post(f"/api/v1/intervenciones/{plan_nuevo}/seguimiento",
                 headers=_cab(token_especialista),
                 json={"estado_reportado": "EN_TIEMPO",
                       "avance_nota": "Una nota de avance cualquiera."})

    from comun.datos import consultar
    acciones = {f["accion"] for f in consultar(
        "SELECT DISTINCT accion FROM auditoria.bitacora "
        " WHERE recurso_id = %s", (str(plan_nuevo),))}
    assert {"INTERVENCION_APROBADA", "INTERVENCION_ESTADO_CAMBIADO",
            "INTERVENCION_AVANCE"} <= acciones, acciones
    # Y el codigo que es un permiso NO se usa como accion.
    assert "INTERVENCION_SEGUIMIENTO" not in acciones, (
        "INTERVENCION_SEGUIMIENTO es un permiso, no una accion. Usarlo como "
        "accion deja la bitacora ambigua: quien filtre por el no sabe si ve "
        "«alguien uso el permiso» o «alguien registro un avance».")
