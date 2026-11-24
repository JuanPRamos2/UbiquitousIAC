"""
Pruebas de algorithms-service, el motor de reglas.

Las tres que importan de verdad no comprueban que el motor «funcione», sino
que no miente:

  * evaluar el riesgo no gasta presupuesto de privacidad;
  * una detección nunca sale sin su explicación;
  * las unidades que el motor NO pudo evaluar se reportan, porque omitirlas
    haría creer a la organización que ahí no hay riesgo.
"""
import os

import pytest
from conftest import cab


def test_salud_y_contrato(algoritmos):
    assert algoritmos.get("/health/live").status_code == 200
    r = algoritmos.get("/health/ready")
    assert r.status_code == 200, r.get_data(as_text=True)
    assert set(r.get_json()["dependencias"]) >= {"postgresql", "mongodb", "redis"}

    c = algoritmos.get("/openapi.json")
    assert c.status_code == 200
    contrato = c.get_json()
    assert len(contrato["components"]["responses"]) == 7
    assert contrato["components"]["securitySchemes"]["bearerAuth"]
    assert algoritmos.get("/docs").status_code == 200


def test_sin_token_no_se_entra(algoritmos):
    assert algoritmos.get("/api/v1/algoritmos/reglas").status_code == 401
    assert algoritmos.post("/api/v1/algoritmos/evaluar",
                           json={"campania_id": "CAMP-2026-S1"}).status_code == 401


def test_las_reglas_traen_su_condicion_en_palabras(algoritmos, token_especialista):
    """Una regla cuyo efecto solo se entiende leyendo el código no es auditable."""
    r = algoritmos.get("/api/v1/algoritmos/reglas", headers=cab(token_especialista))
    assert r.status_code == 200
    reglas = r.get_json()["reglas"]
    assert len(reglas) >= 4
    for regla in reglas:
        assert regla["condicion_legible"], regla["regla_id"]
        assert len(regla["condicion_legible"]) > 40, (
            f"{regla['regla_id']}: la condicion legible es demasiado corta "
            f"para explicar algo")
        assert regla["nivel"] in ("INFORMATIVO", "ATENCION", "PRIORITARIO")
    # Las intervenciones sugeridas son organizacionales, no personales.
    sugerencias = [s for regla in reglas for s in regla["intervenciones_sugeridas"]]
    assert sugerencias
    assert not any("PERSONA" in s or "EMPLEADO" in s for s in sugerencias)


def test_evaluar_no_gasta_presupuesto_de_privacidad(algoritmos, consultas,
                                                    token_especialista,
                                                    token_admin):
    """La prueba central del servicio.

    Se lee el presupuesto, se corre el motor sobre la campaña completa, y se
    vuelve a leer: el épsilon consumido tiene que ser idéntico. Si el motor
    recalculara agregados para evaluar, cada corrida gastaría privacidad y
    evaluar el riesgo de la organización costaría la capacidad de publicar
    resultados nuevos.
    """
    antes = consultas.get("/api/v1/consultas/presupuesto",
                          headers=cab(token_admin))
    assert antes.status_code == 200
    gasto_antes = sum(float(e["epsilon_consumido"])
                      for e in antes.get_json()["elementos"])

    for _ in range(3):
        r = algoritmos.post("/api/v1/algoritmos/evaluar",
                            headers=cab(token_especialista),
                            json={"campania_id": "CAMP-2026-S1"})
        assert r.status_code == 201, r.get_data(as_text=True)
        assert r.get_json()["epsilon_consumido"] == 0

    consultas.post("/api/v1/consultas/cache/invalidar",
                   headers=cab(token_admin), json={"recurso": "presupuesto"})
    despues = consultas.get("/api/v1/consultas/presupuesto",
                            headers=cab(token_admin))
    gasto_despues = sum(float(e["epsilon_consumido"])
                        for e in despues.get_json()["elementos"])
    assert gasto_despues == gasto_antes, (
        "correr el motor de reglas gasto presupuesto de privacidad: esta "
        "recalculando agregados en lugar de leer los publicados")


def test_ninguna_deteccion_sale_sin_explicacion(algoritmos, token_especialista):
    r = algoritmos.post("/api/v1/algoritmos/evaluar",
                        headers=cab(token_especialista),
                        json={"campania_id": "CAMP-2026-S1"})
    assert r.status_code == 201
    corrida = r.get_json()
    assert corrida["total_detecciones"] > 0, (
        "la base de demostracion debe producir detecciones")
    for d in corrida["detecciones"]:
        assert d.get("explicacion"), d
        assert len(d["explicacion"]) > 30, d["explicacion"]
        # La explicacion tiene que citar el valor observado o la campania:
        # un texto generico no explica nada.
        assert (str(d["valor_observado"])[:4] in d["explicacion"]
                or "campania" in d["explicacion"].lower()), d["explicacion"]


def test_las_unidades_no_evaluables_se_reportan(algoritmos, token_especialista):
    """Omitirlas haría creer que ahí no hay riesgo.

    La base de demostración tiene unidades con todos sus agregados
    suprimidos por el umbral k. El motor no puede concluir nada de ellas, y
    eso tiene que decirlo.
    """
    r = algoritmos.post("/api/v1/algoritmos/evaluar",
                        headers=cab(token_especialista),
                        json={"campania_id": "CAMP-2026-S1"})
    corrida = r.get_json()
    assert corrida["total_no_evaluables"] > 0, (
        "la base de demostracion debe traer unidades con agregados suprimidos")
    for u in corrida["no_evaluables"]:
        assert u["publicados"] == 0
        assert u["motivo"], u
        motivo = u["motivo"].lower()
        assert ("no significa que no haya riesgo" in motivo
                or "sin agregados" in motivo), u["motivo"]


def test_la_cobertura_distingue_no_ver_de_no_encontrar(algoritmos,
                                                       token_especialista):
    r = algoritmos.get("/api/v1/algoritmos/cobertura?campania_id=CAMP-2026-S1",
                       headers=cab(token_especialista))
    assert r.status_code == 200
    c = r.get_json()
    assert c["unidades_convocadas"] > 0
    assert (c["unidades_evaluables"] + c["unidades_no_evaluables"]
            == c["unidades_convocadas"])
    assert 0 < c["cobertura_porcentaje"] <= 100
    assert "no es una unidad sin riesgo" in c["nota"]


def test_cobertura_de_campania_inexistente(algoritmos, token_especialista):
    r = algoritmos.get("/api/v1/algoritmos/cobertura?campania_id=CAMP-NO-EXISTE",
                       headers=cab(token_especialista))
    assert r.status_code == 404
    assert r.get_json()["error"]["codigo"] == "NO_ENCONTRADO"


def test_evaluar_valida_sus_parametros(algoritmos, token_especialista):
    r = algoritmos.post("/api/v1/algoritmos/evaluar",
                        headers=cab(token_especialista), json={})
    assert r.status_code == 422
    assert r.get_json()["error"]["detalles"][0]["campo"] == "campania_id"

    r2 = algoritmos.post("/api/v1/algoritmos/evaluar",
                         headers=cab(token_especialista),
                         json={"campania_id": "CAMP-NO-EXISTE"})
    assert r2.status_code == 422


# ============================================================ simulación
def test_la_simulacion_reacciona_al_umbral_y_no_escribe(algoritmos, token_admin):
    """Mover el umbral tiene que cambiar el resultado, y no crear detecciones.

    Se comprueba contra la base: el número de detecciones de esa regla no
    sube después de simular. Una simulación que dejara detecciones reales
    contaminaría el histórico con escenarios que nunca ocurrieron.
    """
    import psycopg2
    cn = psycopg2.connect(host=os.environ["PG_HOST"], dbname=os.environ["PG_BASE"],
                          user=os.environ["PG_USUARIO"],
                          password=os.environ["PG_CLAVE"])

    def detecciones_de(regla):
        with cn, cn.cursor() as cur:
            cur.execute("SELECT count(*) FROM riesgo.deteccion WHERE regla_id = %s",
                        (regla,))
            return cur.fetchone()[0]

    antes = detecciones_de("RG-02")

    # DIM-RECUP en la campania de demostracion va de 3.45 a 4.00, asi que un
    # umbral de 3.0 no detecta nada y uno de 4.0 detecta todo. Si el
    # comparador estuviera invertido, los dos darian lo mismo.
    bajo = algoritmos.post("/api/v1/algoritmos/simular", headers=cab(token_admin),
                           json={"regla_id": "RG-02",
                                 "campania_id": "CAMP-2026-S1",
                                 "umbral_valor": 3.0})
    alto = algoritmos.post("/api/v1/algoritmos/simular", headers=cab(token_admin),
                           json={"regla_id": "RG-02",
                                 "campania_id": "CAMP-2026-S1",
                                 "umbral_valor": 4.0})
    assert bajo.status_code == alto.status_code == 200
    assert bajo.get_json()["detectadas_con_umbral_simulado"] == 0
    assert alto.get_json()["detectadas_con_umbral_simulado"] > 0
    assert len(alto.get_json()["entrarian"]) > 0
    assert alto.get_json()["epsilon_consumido"] == 0

    assert detecciones_de("RG-02") == antes, (
        "la simulacion creo detecciones: tiene que ser de solo lectura")
    cn.close()


def test_la_simulacion_marca_lo_que_esta_cerca_del_ruido(algoritmos, token_admin):
    """Una unidad cerca del ruido entra o sale del umbral por azar."""
    r = algoritmos.post("/api/v1/algoritmos/simular", headers=cab(token_admin),
                        json={"regla_id": "RG-02",
                              "campania_id": "CAMP-2026-S1",
                              "umbral_valor": 4.0})
    s = r.get_json()
    assert s["con_advertencia_de_precision"] >= 0
    assert "azar" in s["nota"]


def test_una_regla_de_tendencia_no_se_simula(algoritmos, token_admin):
    """RG-04 evalúa deterioro sostenido: no hay un umbral que mover."""
    r = algoritmos.post("/api/v1/algoritmos/simular", headers=cab(token_admin),
                        json={"regla_id": "RG-04", "campania_id": "CAMP-2026-S1"})
    assert r.status_code == 400
    assert r.get_json()["error"]["codigo"] == "OPERACION_NO_PERMITIDA"
    assert "tendencia" in r.get_json()["error"]["mensaje"]


def test_regla_inexistente(algoritmos, token_admin):
    r = algoritmos.post("/api/v1/algoritmos/simular", headers=cab(token_admin),
                        json={"regla_id": "RG-99", "campania_id": "CAMP-2026-S1"})
    assert r.status_code == 404


# ================================================================ alcance
def test_el_lider_solo_ve_su_subarbol(algoritmos, token_lider):
    """El alcance se resuelve contra la jerarquía, no contra el parámetro."""
    r = algoritmos.get("/api/v1/algoritmos/detecciones"
                       "?unidad_organizacional_id=UO-LOG-TURNO-A",
                       headers=cab(token_lider))
    assert r.status_code == 403
    assert r.get_json()["error"]["codigo"] == "FUERA_DE_ALCANCE"

    propia = algoritmos.get("/api/v1/algoritmos/detecciones"
                            "?unidad_organizacional_id=UO-CC-TURNO-B",
                            headers=cab(token_lider))
    assert propia.status_code == 200


def test_sin_filtro_el_lider_tampoco_ve_otras_unidades(algoritmos, token_lider):
    """El alcance se aplica también al resultado, no solo al parámetro."""
    r = algoritmos.get("/api/v1/algoritmos/detecciones?tamano=100",
                       headers=cab(token_lider))
    assert r.status_code == 200
    unidades = {d["unidad_organizacional_id"] for d in r.get_json()["detecciones"]}
    assert unidades <= {"UO-CC-TURNO-B"}, (
        f"el lider vio detecciones de unidades ajenas: {sorted(unidades)}")


def test_el_colaborador_no_consulta_detecciones(algoritmos, token_colaborador):
    r = algoritmos.get("/api/v1/algoritmos/detecciones",
                       headers=cab(token_colaborador))
    assert r.status_code == 403
    assert r.get_json()["error"]["codigo"] == "SIN_PERMISO"


def test_el_colaborador_no_corre_el_motor(algoritmos, token_colaborador):
    r = algoritmos.post("/api/v1/algoritmos/evaluar",
                        headers=cab(token_colaborador),
                        json={"campania_id": "CAMP-2026-S1"})
    assert r.status_code == 403


def test_nivel_invalido_se_rechaza(algoritmos, token_especialista):
    r = algoritmos.get("/api/v1/algoritmos/detecciones?nivel=URGENTISIMO",
                       headers=cab(token_especialista))
    assert r.status_code == 400
    assert r.get_json()["error"]["codigo"] == "PARAMETRO_INVALIDO"


# =============================================================== corridas
def test_la_corrida_queda_guardada_en_mongodb(algoritmos, token_especialista):
    """MongoDB es donde el proyecto almacena los resultados de algoritmos.

    Sin ese registro, una detección de hace tres meses no se puede explicar,
    porque los umbrales pudieron cambiar desde entonces.
    """
    r = algoritmos.post("/api/v1/algoritmos/evaluar",
                        headers=cab(token_especialista),
                        json={"campania_id": "CAMP-2026-S1",
                              "unidad_organizacional_id": "UO-CC-TURNO-B"})
    assert r.status_code == 201
    cid = r.get_json()["corrida_id"]
    assert cid.startswith("ALG-")

    detalle = algoritmos.get(f"/api/v1/algoritmos/corridas/{cid}",
                             headers=cab(token_especialista))
    assert detalle.status_code == 200
    guardada = detalle.get_json()
    assert guardada["campania_id"] == "CAMP-2026-S1"
    assert "detecciones" in guardada
    assert guardada["epsilon_consumido"] == 0

    listado = algoritmos.get("/api/v1/algoritmos/corridas?tamano=5",
                             headers=cab(token_especialista))
    assert listado.status_code == 200
    assert listado.get_json()["paginacion"]["total"] >= 1
    # El listado no arrastra las detecciones: serian cientos por pagina.
    assert all("detecciones" not in c for c in listado.get_json()["corridas"])


def test_corrida_inexistente(algoritmos, token_especialista):
    r = algoritmos.get("/api/v1/algoritmos/corridas/ALG-000000000000",
                       headers=cab(token_especialista))
    assert r.status_code == 404


def test_correr_el_motor_queda_en_la_bitacora(algoritmos, token_especialista):
    """La bitácora tiene llave foránea contra auditoria.tipo_accion.

    Si DETECCION_EVALUADA no estuviera declarado en la migración 006, la
    inserción fallaría en silencio y correr el motor no dejaría rastro.
    """
    import psycopg2
    algoritmos.post("/api/v1/algoritmos/evaluar", headers=cab(token_especialista),
                    json={"campania_id": "CAMP-2026-S1",
                          "unidad_organizacional_id": "UO-CC-TURNO-B"})
    cn = psycopg2.connect(host=os.environ["PG_HOST"], dbname=os.environ["PG_BASE"],
                          user=os.environ["PG_USUARIO"],
                          password=os.environ["PG_CLAVE"])
    with cn, cn.cursor() as cur:
        cur.execute("SELECT count(*) FROM auditoria.bitacora "
                    " WHERE accion = 'DETECCION_EVALUADA'")
        n = cur.fetchone()[0]
    cn.close()
    assert n >= 1, ("algorithms-service no pudo escribir en la bitacora: "
                    "falta aplicar la migracion 006")
