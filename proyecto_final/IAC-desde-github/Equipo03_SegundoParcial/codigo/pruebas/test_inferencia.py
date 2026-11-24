"""
Control de consultas repetidas y de ataques por diferencia.

QUÉ SE PRUEBA Y POR QUÉ IMPORTA
-------------------------------
El proyecto afirma que ningún resultado permite llegar a una persona. Hasta
ahora eso se sostenía en dos mecanismos que miran UNA consulta a la vez: el
umbral k y el ruido de Laplace. Ninguno de los dos ve la combinación de dos
consultas, y hay información que ninguna revela por separado y que la resta
de ambas sí revela.

Estas pruebas comprueban que el hueco está cerrado, y una de ellas —la del
árbol— comprueba además que el control sigue siendo EFECTIVO, no solo que
existe: un control que nunca bloquea pasa cualquier prueba que se limite a
llamarlo.
"""
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "apps", "microservicios", "comun"))

from comun import ErrorApi  # noqa: E402
from comun.datos import consultar, consultar_uno  # noqa: E402
from comun.inferencia import (REPETICIONES_ANORMALES,  # noqa: E402
                              _comprobar_residuo, k_minimo,
                              registrar_consulta, registrar_unidad,
                              unidades_consultadas, verificar_conjunto,
                              verificar_diferencia)


@pytest.fixture
def actor(redis_limpio):
    """Un actor nuevo por prueba: el control lleva estado por actor."""
    import uuid
    return f"PRUEBA-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def redis_limpio():
    import redis
    r = redis.Redis(host=os.environ.get("REDIS_HOST", "127.0.0.1"))
    for clave in r.scan_iter("inferencia:*"):
        r.delete(clave)
    return r


# =========================================================================
# El dato del que depende todo el control
# =========================================================================

def test_ninguna_unidad_padre_es_mas_chica_que_sus_hijas():
    """Si el padre declara menos gente que sus hijas, el control no sirve.

    El residuo que decide si una consulta se bloquea se calcula como
    «plantilla del padre − suma de las hijas ya consultadas». Con un padre
    más chico que sus hijas ese número sale negativo y la condición
    `0 < residuo < k` no se cumple nunca: el control queda presente y sin
    efecto, que es la peor de las tres posibilidades.

    Pasó de verdad: UO-OPERACIONES declaraba 120 personas y sus quince
    unidades hijas sumaban 1,186. Lo corrige la migración 008.
    """
    malas = consultar("SELECT * FROM gobernanza.fn_jerarquia_consistente()")
    assert not malas, (
        "Estas unidades declaran menos plantilla que la suma de sus hijas, "
        f"y eso deja sin efecto el control de inferencia: {malas}")


# =========================================================================
# Ataque por diferencia
# =========================================================================

def test_una_sola_consulta_nunca_se_bloquea(actor, redis_limpio):
    """Sin consultas previas no hay nada que restar."""
    k = k_minimo(consultar_uno)
    verificar_diferencia(redis_limpio, actor, "UO-CC-TURNO-B", consultar_uno, k)


def test_el_umbral_del_residuo_es_exacto():
    """Dónde bloquea y dónde no, probado sobre el cálculo mismo.

    Esta prueba no toca la base: le da a `_comprobar_residuo` un padre
    publicado inventado y comprueba las tres fronteras. Va sobre el
    cálculo a propósito, porque es donde estaba el defecto —no en el SQL
    sino en QUÉ se restaba— y porque con los datos sembrados la ruta
    completa no se puede recorrer (ver la prueba siguiente).
    """
    k = 5

    def padre_con_residuo(residuo):
        """Simula la consulta del residuo peor del padre."""
        def falso(sql, params=None):
            if "resultado_protegido" not in sql:
                return None
            if 0 < residuo < k:
                return {"campania_id": "CAMP-2026-S1",
                        "dimension_id": "DIM-CARGA", "residuo": residuo}
            # La consulta real filtra con WHERE residuo > 0 AND < k, así
            # que un residuo fuera de rango no devuelve fila.
            return None
        return falso

    # Residuo de 0: las hijas cubren al padre completo, nadie queda aislado.
    _comprobar_residuo(padre_con_residuo(0), "UO-PADRE",
                       {"UO-PADRE", "UO-HIJA"}, k, "UO-HIJA")

    # Residuo >= k: queda un grupo, pero es lo bastante grande.
    _comprobar_residuo(padre_con_residuo(k), "UO-PADRE",
                       {"UO-PADRE", "UO-HIJA"}, k, "UO-HIJA")

    # Residuo pequeño pero positivo: ahí sí.
    for residuo in (1, k - 1):
        with pytest.raises(ErrorApi) as caja:
            _comprobar_residuo(padre_con_residuo(residuo), "UO-PADRE",
                               {"UO-PADRE", "UO-HIJA"}, k, "UO-HIJA")
        error = caja.value
        assert error.codigo == "INFERENCIA_BLOQUEADA"
        assert error.http == 403
        # El error dice CUÁNTOS se habrían aislado, en qué campaña y contra
        # qué umbral. Sin eso, quien lo recibe no puede distinguirlo de un
        # permiso faltante.
        campos = {d["campo"]: d["problema"] for d in error.detalles}
        assert int(campos["residuo_respondientes"]) == residuo
        assert int(campos["umbral_k"]) == k
        assert campos["campania"] == "CAMP-2026-S1"
        # Y habla de respondientes, no de plantilla: es la cantidad que un
        # atacante puede despejar por resta.
        assert "respondiente" in error.mensaje


def test_con_los_datos_sembrados_no_hay_nada_que_bloquear(actor, redis_limpio):
    """El estado real del sistema, dicho en una prueba y no en un comentario.

    Ninguna unidad publicada es padre de otra: solo se agregan las hojas
    del árbol. Sin un agregado de nivel superior publicado no hay minuendo
    que restar, así que recorrer el padre y todas sus hijas NO bloquea
    nada — y eso es correcto, porque no hay nada que filtrar.

    La versión anterior de esta prueba afirmaba lo contrario: restaba
    `plantilla_declarada` y daba por demostrado que el ataque quedaba
    bloqueado. Lo que demostraba era el bloqueo de una consulta
    inofensiva. Se deja escrito aquí para que nadie vuelva a leer un
    bloqueo como prueba de una fuga evitada.
    """
    publicadas_que_son_padre = consultar(
        "SELECT DISTINCT r.unidad_organizacional_id "
        "  FROM agregado.resultado_protegido r "
        " WHERE r.valor_protegido IS NOT NULL "
        "   AND EXISTS (SELECT 1 FROM organizacion.unidad_organizacional h "
        "                WHERE h.unidad_padre_id = r.unidad_organizacional_id)")
    assert not publicadas_que_son_padre, (
        f"Ya hay unidades publicadas que son padre de otras: "
        f"{[f['unidad_organizacional_id'] for f in publicadas_que_son_padre]}. "
        f"El ataque por diferencia pasa a ser posible, y esta prueba hay que "
        f"cambiarla por una que recorra el arbol y exija el bloqueo.")

    k = k_minimo(consultar_uno)
    padre = "UO-OPERACIONES"
    hijas = [f["unidad_organizacional_id"] for f in consultar(
        "SELECT unidad_organizacional_id FROM organizacion.unidad_organizacional "
        " WHERE unidad_padre_id = %s ORDER BY plantilla_declarada DESC", (padre,))]
    assert len(hijas) > 3, "La prueba necesita un árbol con varias hijas"

    registrar_unidad(redis_limpio, actor, padre)
    for hija in hijas:
        # No debe lanzar: el padre no está publicado.
        verificar_diferencia(redis_limpio, actor, hija, consultar_uno, k)
        registrar_unidad(redis_limpio, actor, hija)


def test_el_umbral_k_cuenta_RESPUESTAS_y_no_plantilla():
    """El hecho que causó el defecto, fijado contra la base.

    El control de inferencia restaba `plantilla_declarada` y afirmaba que
    era «el mismo dato que usa el umbral k al publicar». No lo es:
    `fn_calcular_agregado_protegido` cuenta respuestas distintas. Si
    alguien cambia la función para que cuente otra cosa, esta prueba falla
    y obliga a revisar el control, que es el punto.
    """
    fuente = consultar_uno(
        "SELECT pg_get_functiondef(p.oid) AS cuerpo "
        "  FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
        " WHERE n.nspname = 'agregado' "
        "   AND p.proname = 'fn_calcular_agregado_protegido'")
    assert fuente, "No existe agregado.fn_calcular_agregado_protegido"
    cuerpo = fuente["cuerpo"].lower()
    assert "count(distinct" in cuerpo and "respuesta" in cuerpo, (
        "La supresion por umbral k ya no cuenta respuestas distintas. "
        "comun.inferencia resta respondientes porque ESTA funcion los "
        "cuenta: si cambio, hay que revisar el control.")
    assert "plantilla_declarada" not in cuerpo, (
        "La publicacion ahora mira plantilla_declarada. Si el umbral k "
        "pasa a depender de la plantilla, el control de inferencia tiene "
        "que restar lo mismo.")


def test_dos_actores_no_se_contaminan(redis_limpio):
    """El estado es por actor: lo que uno consultó no bloquea al otro."""
    k = k_minimo(consultar_uno)
    hijas = [f["unidad_organizacional_id"] for f in consultar(
        "SELECT unidad_organizacional_id FROM organizacion.unidad_organizacional "
        " WHERE unidad_padre_id = 'UO-OPERACIONES' ORDER BY plantilla_declarada DESC")]

    registrar_unidad(redis_limpio, "ACTOR-A", "UO-OPERACIONES")
    for hija in hijas[:-1]:
        registrar_unidad(redis_limpio, "ACTOR-A", hija)

    # ACTOR-B no ha consultado nada: la misma unidad no le puede bloquear.
    verificar_diferencia(redis_limpio, "ACTOR-B", hijas[-1], consultar_uno, k)
    assert unidades_consultadas(redis_limpio, "ACTOR-B") == set()


def test_las_hijas_que_cubren_al_padre_no_bloquean(actor, redis_limpio):
    """Residuo cero es inofensivo, y la distinción no es un detalle.

    Si las hijas consultadas cubren al padre completo no queda nadie
    aislado. Un control que bloqueara por «residuo pequeño» sin distinguir
    el cero negaría consultas legítimas, que es la forma más rápida de que
    alguien lo desactive.
    """
    k = k_minimo(consultar_uno)
    fila = consultar_uno(
        "SELECT padre.unidad_organizacional_id AS padre "
        "  FROM organizacion.unidad_organizacional padre "
        "  JOIN organizacion.unidad_organizacional hija "
        "    ON hija.unidad_padre_id = padre.unidad_organizacional_id "
        " GROUP BY padre.unidad_organizacional_id, padre.plantilla_declarada "
        "HAVING padre.plantilla_declarada = coalesce(sum(hija.plantilla_declarada),0) "
        " LIMIT 1")
    if not fila:
        pytest.skip("No hay en los datos un padre que iguale a sus hijas")

    padre = fila["padre"]
    hijas = [f["unidad_organizacional_id"] for f in consultar(
        "SELECT unidad_organizacional_id FROM organizacion.unidad_organizacional "
        " WHERE unidad_padre_id = %s", (padre,))]
    registrar_unidad(redis_limpio, actor, padre)
    for hija in hijas[:-1]:
        registrar_unidad(redis_limpio, actor, hija)
    verificar_diferencia(redis_limpio, actor, hijas[-1], consultar_uno, k)


# =========================================================================
# Consultas repetidas
# =========================================================================

def test_la_repeticion_se_cuenta_por_actor_y_por_parametros(actor, redis_limpio):
    """Cambiar un parámetro es otra consulta, no una repetición."""
    for i in range(1, 4):
        n = registrar_consulta(redis_limpio, actor, "tablero", {"u": "A"})
        assert n == i
    # Otros parámetros: cuenta aparte.
    assert registrar_consulta(redis_limpio, actor, "tablero", {"u": "B"}) == 1
    # Otro recurso: cuenta aparte.
    assert registrar_consulta(redis_limpio, actor, "tendencia", {"u": "A"}) == 1


def test_la_repeticion_no_bloquea_nunca(actor, redis_limpio):
    """Es un registro, no un límite. La distinción es deliberada.

    En este sistema el ruido se aplica UNA vez, al publicar, y se guarda:
    repetir la consulta devuelve el mismo valor, así que no hay mil valores
    distintos que promediar para cancelar el ruido. Bloquear la repetición
    daría una falsa sensación de protección contra un ataque que el diseño
    ya cerró por otra vía, y estorbaría a quien recarga una pantalla.

    El límite de velocidad existe aparte, en `limite_consumo`.
    """
    for _ in range(REPETICIONES_ANORMALES + 10):
        registrar_consulta(redis_limpio, actor, "tablero", {"u": "A"})
    k = k_minimo(consultar_uno)
    verificar_diferencia(redis_limpio, actor, "UO-CC-TURNO-B", consultar_uno, k)


def test_sin_redis_el_control_no_niega_el_servicio(actor):
    """Una caída de la caché no puede convertirse en denegación.

    Este control detecta exploración; no es la última línea de defensa. El
    umbral k y el ruido siguen aplicándose en la base pase lo que pase con
    Redis, así que negar el servicio aquí sería un remedio peor que la
    enfermedad.
    """
    class RedisCaido:
        def hincrby(self, *a, **k): raise RuntimeError("sin redis")
        def expire(self, *a, **k): raise RuntimeError("sin redis")
        def sadd(self, *a, **k): raise RuntimeError("sin redis")
        def smembers(self, *a, **k): raise RuntimeError("sin redis")

    caido = RedisCaido()
    assert registrar_consulta(caido, actor, "tablero", {"u": "A"}) == 0
    registrar_unidad(caido, actor, "UO-OPERACIONES")      # no lanza
    verificar_diferencia(caido, actor, "UO-CC-TURNO-B", consultar_uno,
                         k_minimo(consultar_uno))          # no lanza


# =========================================================================
# El servicio lo usa de verdad
# =========================================================================

def test_queries_service_aplica_el_control_antes_de_leer():
    """Verificar después de leer deja el dato ya calculado en memoria.

    El orden importa: si se verificara al final, lo único que faltaría para
    que el dato salga es no enviarlo, y basta un error de programación más
    adelante para que salga igual.
    """
    ruta = os.path.join(RAIZ, "apps", "microservicios", "queries-service", "app.py")
    fuente = open(ruta, encoding="utf-8").read()
    assert "_control_inferencia" in fuente, (
        "queries-service no usa el control: el módulo existiría sin efecto.")

    cuerpo = fuente[fuente.index("def tablero_unidad"):]
    cuerpo = cuerpo[:cuerpo.index("@app.get")]
    assert cuerpo.index("_control_inferencia") < cuerpo.index("def consulta"), (
        "El control tiene que correr ANTES de armar la consulta a la base.")
