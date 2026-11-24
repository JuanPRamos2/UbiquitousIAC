"""
trends-service — análisis longitudinal.

LA PREGUNTA QUE SE PRUEBA AQUÍ
------------------------------
Una unidad pasó de 3.4 a 3.2. ¿Empeoró, o es ruido?

Todos los valores publicados llevan ruido de Laplace, así que esa caída de
0.2 puede ser una señal verdadera o puede ser enteramente azar, según
cuánto ruido se le aplicó al publicar. Un tablero que dibuje las dos
situaciones igual lleva a intervenir sobre una unidad en la que no pasó
nada, y a no intervenir en una en la que sí.

Estas pruebas comprueban las dos mitades del asunto, y la segunda importa
tanto como la primera:

  · que un cambio grande se reporte como real;
  · que un cambio pequeño NO se reporte como real.

Un servicio que marcara todo como tendencia pasaría cualquier prueba que
solo mirara la primera mitad, y sería inútil: reportar todo equivale a no
reportar nada.
"""
import math
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVICIO = os.path.join(RAIZ, "apps", "microservicios", "trends-service")


@pytest.fixture(scope="module")
def tendencias():
    """El servicio en memoria, con PostgreSQL real detrás.

    Se carga con `_cargar` de conftest y NO agregando la carpeta del
    servicio a sys.path. La diferencia no es de estilo: cada servicio
    tiene su propio `app.py` y su propio `contrato.py`, así que dejar una
    de esas carpetas en la ruta de búsqueda hace que el siguiente
    `import app` de la suite resuelva al servicio equivocado. Pasó: estas
    pruebas solas pasaban, y corridas junto con las del portal lo
    rompían.
    """
    from conftest import _cargar
    modulo = _cargar("trends-service", "svc_trends")
    modulo.app.config["TESTING"] = True
    return modulo


@pytest.fixture
def cliente(tendencias):
    return tendencias.app.test_client()


# =========================================================================
# El criterio: lo que convierte al servicio en algo discutible
# =========================================================================

def test_el_criterio_esta_publicado(cliente, token_especialista):
    """Un clasificador que no dice con qué regla decide es una caja negra.

    Y una caja negra no se puede discutir en un comité ni defender ante la
    unidad que recibe una intervención por su causa.
    """
    r = cliente.get("/api/v1/tendencias/criterio",
                    headers={"Authorization": f"Bearer {token_especialista}"})
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()

    assert d["factor_ruido"] == pytest.approx(math.sqrt(2), rel=1e-6)
    assert "sqrt(2)" in d["regla"]
    assert d["minimo_puntos_para_tendencia"] >= 3, (
        "Con dos puntos, cualquier par de valores define una 'tendencia' que "
        "puede ser enteramente azar.")

    # Los límites también se publican. Un servicio que solo publica sus
    # aciertos invita a usarlo para lo que no sirve.
    limites = " ".join(d["limites_conocidos"]).lower()
    assert "no es una prueba de hipotesis" in limites
    assert "extrapol" in limites

    # Analizar no gasta privacidad: lee lo ya publicado.
    assert d["epsilon_consumido"] == 0.0


# =========================================================================
# La decisión real / ruido
# =========================================================================

def test_un_cambio_dentro_del_ruido_no_se_reporta_como_real(tendencias):
    """La mitad que un servicio complaciente omitiría."""
    serie = tendencias._analizar([
        {"campania_id": "C1", "secuencia": 1, "valor_protegido": 3.40,
         "escala_ruido": 0.50, "n_observaciones": 40},
        {"campania_id": "C2", "secuencia": 2, "valor_protegido": 3.20,
         "escala_ruido": 0.50, "n_observaciones": 40},
    ])
    segundo = serie[1]
    # |3.20 - 3.40| = 0.20 ; umbral = sqrt(2)*0.50 = 0.707
    assert segundo["cambio"] == pytest.approx(-0.20, abs=1e-9)
    assert segundo["supera_el_ruido"] is False
    assert "dentro del ruido" in segundo["lectura"]
    assert "no se puede afirmar" in segundo["lectura"].lower()


def test_un_cambio_por_encima_del_ruido_si_se_reporta(tendencias):
    serie = tendencias._analizar([
        {"campania_id": "C1", "secuencia": 1, "valor_protegido": 4.00,
         "escala_ruido": 0.10, "n_observaciones": 120},
        {"campania_id": "C2", "secuencia": 2, "valor_protegido": 3.00,
         "escala_ruido": 0.10, "n_observaciones": 120},
    ])
    segundo = serie[1]
    assert segundo["supera_el_ruido"] is True
    assert segundo["cambio"] == pytest.approx(-1.0, abs=1e-9)
    assert "bajo" in segundo["lectura"].lower()


def test_el_umbral_usa_el_ruido_MAYOR_de_los_dos_puntos(tendencias):
    """Con el menor, un punto muy ruidoso se leería como señal.

    Se restan dos valores con ruido independiente: lo que manda es el peor
    de los dos, no el mejor.
    """
    serie = tendencias._analizar([
        {"campania_id": "C1", "secuencia": 1, "valor_protegido": 3.0,
         "escala_ruido": 0.05, "n_observaciones": 200},
        {"campania_id": "C2", "secuencia": 2, "valor_protegido": 3.6,
         "escala_ruido": 0.60, "n_observaciones": 9},
    ])
    segundo = serie[1]
    assert segundo["umbral_de_ruido"] == pytest.approx(
        math.sqrt(2) * 0.60, abs=1e-3)
    # 0.6 de cambio contra un umbral de 0.848: no alcanza.
    assert segundo["supera_el_ruido"] is False


# =========================================================================
# Los puntos suprimidos
# =========================================================================

def test_un_punto_suprimido_no_se_quita_ni_se_interpola(tendencias):
    """Quitarlo juntaría dos campañas no consecutivas en un solo paso.

    Y ese paso se leería como un cambio que nunca ocurrió entre ellas.
    """
    serie = tendencias._analizar([
        {"campania_id": "C1", "secuencia": 1, "valor_protegido": 3.0,
         "escala_ruido": 0.1, "n_observaciones": 50},
        {"campania_id": "C2", "secuencia": 2, "valor_protegido": None,
         "escala_ruido": None, "n_observaciones": 2},
        {"campania_id": "C3", "secuencia": 3, "valor_protegido": 3.1,
         "escala_ruido": 0.1, "n_observaciones": 50},
    ])
    assert len(serie) == 3, "La serie conserva el punto suprimido."

    suprimido = serie[1]
    assert suprimido["publicado"] is False
    assert suprimido["valor_protegido"] is None
    assert suprimido["cambio"] is None
    assert suprimido["supera_el_ruido"] is None
    assert "no es cero" in suprimido["lectura"].lower()

    # El tercero se compara contra el PRIMERO publicado, no contra el hueco.
    tercero = serie[2]
    assert tercero["campania_comparada"] == "C1"
    assert tercero["cambio"] == pytest.approx(0.1, abs=1e-9)


def test_una_serie_toda_suprimida_no_inventa_tendencia(tendencias):
    serie = tendencias._analizar([
        {"campania_id": f"C{i}", "secuencia": i, "valor_protegido": None,
         "escala_ruido": None, "n_observaciones": 1} for i in range(1, 4)])
    resumen = tendencias._resumen(serie)
    assert resumen["campanias_publicadas"] == 0
    assert resumen["campanias_suprimidas"] == 3
    assert resumen["direccion"] == "INDETERMINADA"


# =========================================================================
# El resumen
# =========================================================================

def test_una_serie_plana_con_ruido_no_parece_moverse(tendencias):
    """Contar TODOS los cambios haría que el ruido pareciera movimiento."""
    puntos = []
    for i, v in enumerate([3.00, 3.08, 2.95, 3.05, 2.98], start=1):
        puntos.append({"campania_id": f"C{i}", "secuencia": i,
                       "valor_protegido": v, "escala_ruido": 0.40,
                       "n_observaciones": 60})
    resumen = tendencias._resumen(tendencias._analizar(puntos))
    assert resumen["cambios_sobre_el_ruido"] == 0
    assert resumen["direccion"] == "ESTABLE"
    # La distinción que importa: no es "no cambió", es "si cambió algo, no
    # se distingue del ruido".
    assert "ruido" in resumen["lectura"].lower()


def test_una_caida_sostenida_si_se_detecta(tendencias):
    puntos = []
    for i, v in enumerate([4.50, 4.00, 3.50, 3.00], start=1):
        puntos.append({"campania_id": f"C{i}", "secuencia": i,
                       "valor_protegido": v, "escala_ruido": 0.05,
                       "n_observaciones": 150})
    resumen = tendencias._resumen(tendencias._analizar(puntos))
    assert resumen["cambios_sobre_el_ruido"] == 3
    assert resumen["cambios_a_la_baja"] == 3
    assert resumen["cambios_al_alza"] == 0
    assert resumen["direccion"] == "A_LA_BAJA"


# =========================================================================
# Contra la base real
# =========================================================================

def test_la_serie_de_una_unidad_real_responde(cliente, token_especialista):
    r = cliente.get("/api/v1/tendencias/unidad/UO-CC-TURNO-B",
                    headers={"Authorization": f"Bearer {token_especialista}"})
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    # La serie viene agrupada POR DIMENSIÓN: una unidad no tiene una
    # tendencia, tiene una por cada cosa que se le mide, y promediarlas
    # escondería que la carga empeora mientras el apoyo mejora.
    assert "dimensiones" in d
    assert d["epsilon_consumido"] == 0.0
    for dimension in d["dimensiones"]:
        assert "serie" in dimension and "resumen" in dimension
        for punto in dimension["serie"]:
            # Un punto publicado sin su escala de ruido no se puede
            # interpretar: sin ella no hay con qué comparar el cambio.
            if punto["publicado"]:
                assert punto["escala_ruido"] is not None


def test_una_unidad_que_no_existe_da_404(cliente, token_especialista):
    r = cliente.get("/api/v1/tendencias/unidad/UO-NO-EXISTE",
                    headers={"Authorization": f"Bearer {token_especialista}"})
    assert r.status_code == 404
    assert r.get_json()["error"]["codigo"] == "NO_ENCONTRADO"


def test_un_colaborador_no_consulta_tendencias(cliente, token_colaborador):
    """La autorización la hace el servicio, no el menú que lo llama."""
    r = cliente.get("/api/v1/tendencias/unidad/UO-CC-TURNO-B",
                    headers={"Authorization": f"Bearer {token_colaborador}"})
    assert r.status_code == 403
    assert r.get_json()["error"]["codigo"] == "SIN_PERMISO"


def test_comparar_reporta_las_unidades_que_no_pudo_comparar(cliente,
                                                            token_especialista):
    """La parte que una implementación descuidada omite.

    Una unidad sin valor publicado en alguna de las dos campañas no aparece
    en la comparación. Si no se reporta aparte, quien lee concluye que ahí
    no hubo cambio, cuando lo que pasa es que no se puede saber.
    """
    r = cliente.post("/api/v1/tendencias/comparar",
                     headers={"Authorization": f"Bearer {token_especialista}"},
                     json={"campania_base": "CAMP-2026-S3",
                           "campania_comparada": "CAMP-2026-S4"})
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    assert "comparadas" in d
    assert "sin_comparacion" in d, (
        "Sin esta lista, las unidades que no se pudieron comparar "
        "desaparecen y se leen como 'sin cambio'.")
    for item in d["sin_comparacion"]:
        assert item.get("motivo"), "Cada una tiene que decir POR QUÉ."
    # El motivo distingue «no esta en las dos campanias» de «suprimida»:
    # son dos cosas distintas y la segunda es la que importa.
    motivos = " ".join(i["motivo"] for i in d["sin_comparacion"])
    if d["sin_comparacion"]:
        assert "no es cero" in motivos or "no aparece" in motivos


def test_el_contrato_cubre_todas_las_rutas(tendencias):
    cliente = tendencias.app.test_client()
    contrato = cliente.get("/openapi.json").get_json()
    documentadas = set(contrato["paths"])
    reales = {str(r.rule).replace("<unidad_id>", "{unidad_id}")
              for r in tendencias.app.url_map.iter_rules()
              if "/tendencias/" in str(r.rule)}
    faltan = reales - documentadas
    assert not faltan, f"Rutas sin documentar en el contrato: {faltan}"
