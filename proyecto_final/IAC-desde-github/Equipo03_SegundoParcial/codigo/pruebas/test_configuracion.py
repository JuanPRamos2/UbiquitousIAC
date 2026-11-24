"""
configuration-service — gobierno de los parámetros.

LO QUE MÁS IMPORTA PROBAR
-------------------------
El umbral k es la afirmación central del proyecto. Las pruebas que
cuentan son las que comprueban que no se puede romper:

  · que no se puede bajar de su piso;
  · que no se puede cambiar a mitad de una campaña;
  · que no se puede cambiar sin dejar escrito por qué;
  · que el valor ANTERIOR queda guardado;
  · y que no existe un segundo camino: el rol de la aplicación no tiene
    UPDATE sobre la tabla.

La última es la más fácil de olvidar y la que sostiene a las otras cuatro.
Si el rol pudiera escribir directo, los cuatro controles de arriba serían
una sugerencia.
"""
import os

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def configuracion():
    from conftest import _cargar
    modulo = _cargar("configuration-service", "svc_config")
    modulo.app.config["TESTING"] = True
    return modulo


@pytest.fixture
def cliente(configuracion):
    return configuracion.app.test_client()


def _cab(token):
    return {"Authorization": f"Bearer {token}"}


JUSTIFICACION = ("El comite de privacidad reviso el riesgo de "
                 "reidentificacion y acordo este valor en la sesion del "
                 "trimestre.")


# =========================================================================
# El camino único
# =========================================================================

def test_el_rol_de_la_aplicacion_no_puede_cambiar_un_parametro_directo():
    """La prueba que sostiene a todas las demás.

    Si `bienestar_app` tuviera UPDATE sobre
    `agregado.parametro_privacidad`, existiría un camino para cambiar el
    umbral k sin pasar por la función que escribe el historial, y los
    controles de límite, de campaña abierta y de justificación serían una
    sugerencia.
    """
    from comun.datos import consultar_uno
    permiso = consultar_uno(
        "SELECT has_table_privilege('bienestar_app', "
        "       'agregado.parametro_privacidad', 'UPDATE') AS puede")
    assert permiso["puede"] is False, (
        "El rol de la aplicacion puede hacer UPDATE directo sobre los "
        "parametros de privacidad. Entonces el historial se puede evitar, "
        "y un historial que se puede evitar no es un historial.")


def test_la_funcion_de_cambio_escribe_el_historial_en_la_misma_transaccion():
    """Si fueran dos sentencias, un error entre ellas dejaría el umbral
    cambiado sin fila de historial."""
    from comun.datos import consultar_uno
    fuente = consultar_uno(
        "SELECT pg_get_functiondef(p.oid) AS cuerpo, p.prosecdef AS definer "
        "  FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
        " WHERE n.nspname = 'configuracion' "
        "   AND p.proname = 'fn_cambiar_parametro'")
    assert fuente, "No existe configuracion.fn_cambiar_parametro"
    assert fuente["definer"] is True, (
        "La funcion no es SECURITY DEFINER. Sin eso no puede hacer el "
        "UPDATE que el rol de la aplicacion no tiene permitido, y el "
        "cambio tendria que hacerse por otro camino.")
    cuerpo = fuente["cuerpo"].lower()
    assert "insert into configuracion.cambio_parametro" in cuerpo
    assert "update agregado.parametro_privacidad" in cuerpo
    assert (cuerpo.index("insert into configuracion.cambio_parametro")
            < cuerpo.index("update agregado.parametro_privacidad")), (
        "El UPDATE va antes del INSERT del historial. En la misma "
        "transaccion da igual para la base, pero el orden al leerlo "
        "importa: asi se ve que el historial no es un apunte posterior.")


# =========================================================================
# Leer
# =========================================================================

def test_leer_los_parametros_no_exige_el_permiso_de_cambiarlos(
        cliente, token_especialista):
    """Quien ve un tablero tiene derecho a saber con qué umbral se publicó.

    Esconder el valor de k no protege a nadie: lo que protege es el umbral
    y el ruido. Esto es privacidad diferencial, no seguridad por
    oscuridad.
    """
    r = cliente.get("/api/v1/configuracion/parametros",
                    headers=_cab(token_especialista))
    assert r.status_code == 200, r.get_data(as_text=True)
    claves = {p["clave"] for p in r.get_json()["parametros"]}
    assert "k_umbral_minimo" in claves


def test_cada_parametro_dice_si_se_puede_cambiar_ahora_y_por_que_no(
        cliente, token_admin):
    """Un cliente que lo dedujera cruzando dos campos lo deduciría mal."""
    r = cliente.get("/api/v1/configuracion/parametros",
                    headers=_cab(token_admin))
    d = r.get_json()
    assert d["campanias_abiertas"], (
        "La prueba necesita una campania abierta para probar el congelado.")

    k = next(p for p in d["parametros"] if p["clave"] == "k_umbral_minimo")
    assert k["modificable"] is False
    assert "campania abierta" in k["motivo_no_modificable"]
    assert k["minimo"] == 5
    # Y el motivo del límite viaja con el parámetro: un umbral sin motivo
    # escrito no se puede defender ni discutir.
    assert "afirmacion central" in k["motivo_limite"]


def test_el_historial_trae_el_valor_anterior(cliente, token_admin):
    """Sin el valor anterior no se puede reconstruir con qué umbral se
    publicó cada campaña."""
    r = cliente.get(
        "/api/v1/configuracion/parametros/exportacion_vigencia_horas",
        headers=_cab(token_admin))
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    if not d["historial"]:
        pytest.skip("Todavia no hay cambios registrados de ese parametro")
    fila = d["historial"][0]
    assert "valor_anterior" in fila
    assert fila["valor_nuevo"] is not None
    assert len(fila["justificacion"]) >= 30
    assert "campanias_abiertas" in fila


def test_un_parametro_inexistente_es_404(cliente, token_admin):
    r = cliente.get("/api/v1/configuracion/parametros/no_existe_esto",
                    headers=_cab(token_admin))
    assert r.status_code == 404
    assert r.get_json()["error"]["codigo"] == "PARAMETRO_NO_EXISTE"


# =========================================================================
# Cambiar: los cuatro rechazos
# =========================================================================

def test_no_se_puede_bajar_el_umbral_k_de_su_piso(cliente, token_admin):
    """Por debajo de 5, un agregado de 2 o 3 personas se publica."""
    r = cliente.patch("/api/v1/configuracion/parametros/k_umbral_minimo",
                      headers=_cab(token_admin),
                      json={"valor": 2, "justificacion": JUSTIFICACION})
    assert r.status_code in (409, 422), r.get_data(as_text=True)
    # Con una campaña abierta gana el congelado; sin ella, el límite. Los
    # dos son correctos y los dos impiden el cambio, que es lo que importa.
    assert r.get_json()["error"]["codigo"] in ("FUERA_DE_LIMITE",
                                              "CAMPANIA_ABIERTA")


def test_un_parametro_congelado_no_se_cambia_con_campania_abierta(
        cliente, token_admin):
    """Cambiarlo a mitad produce un tablero con dos criterios."""
    r = cliente.patch("/api/v1/configuracion/parametros/k_umbral_minimo",
                      headers=_cab(token_admin),
                      json={"valor": 8, "justificacion": JUSTIFICACION})
    assert r.status_code == 409, r.get_data(as_text=True)
    error = r.get_json()["error"]
    assert error["codigo"] == "CAMPANIA_ABIERTA"
    # El mensaje dice QUÉ campaña lo bloquea: sin eso, quien lo recibe no
    # sabe a qué esperar.
    assert "CAMP-" in error["mensaje"]


def test_no_se_puede_cambiar_sin_justificacion(cliente, token_admin):
    r = cliente.patch(
        "/api/v1/configuracion/parametros/exportacion_vigencia_horas",
        headers=_cab(token_admin), json={"valor": 24, "justificacion": "porque"})
    assert r.status_code == 422
    campos = {d["campo"] for d in r.get_json()["error"]["detalles"]}
    assert "justificacion" in campos


def test_un_valor_fuera_de_rango_se_rechaza_con_su_motivo(cliente, token_admin):
    r = cliente.patch(
        "/api/v1/configuracion/parametros/exportacion_vigencia_horas",
        headers=_cab(token_admin),
        json={"valor": 99999, "justificacion": JUSTIFICACION})
    assert r.status_code == 422, r.get_data(as_text=True)
    assert r.get_json()["error"]["codigo"] == "FUERA_DE_LIMITE"
    assert "720" in r.get_json()["error"]["mensaje"]


def test_un_cambio_legitimo_funciona_y_queda_registrado(cliente, token_admin):
    """El caso que tiene que seguir siendo posible.

    Un servicio que bloqueara todo también pasaría las pruebas de arriba y
    sería inútil: no se podría ajustar nada nunca.
    """
    from comun.datos import consultar_uno
    antes = consultar_uno("SELECT agregado.fn_parametro("
                          "'exportacion_vigencia_horas') AS v")["v"]
    nuevo = 48 if float(antes) != 48 else 72

    r = cliente.patch(
        "/api/v1/configuracion/parametros/exportacion_vigencia_horas",
        headers=_cab(token_admin),
        json={"valor": nuevo, "justificacion": JUSTIFICACION})
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    assert float(d["valor_anterior"]) == pytest.approx(float(antes))
    assert float(d["valor_nuevo"]) == pytest.approx(nuevo)
    # La respuesta avisa de la confusión más probable y más cara.
    assert "no vuelve a publicar" in d["nota"].lower()

    registrado = consultar_uno(
        "SELECT valor_anterior, valor_nuevo, justificacion, actor_usuario_id "
        "  FROM configuracion.cambio_parametro WHERE cambio_id = %s",
        (d["cambio_id"],))
    assert registrado, "El cambio no quedo en el historial."
    assert float(registrado["valor_anterior"]) == pytest.approx(float(antes))
    assert registrado["actor_usuario_id"]

    # Y se deja la base como estaba.
    cliente.patch(
        "/api/v1/configuracion/parametros/exportacion_vigencia_horas",
        headers=_cab(token_admin),
        json={"valor": float(antes),
              "justificacion": "Se restaura el valor anterior tras la "
                               "prueba automatizada del control de limites."})


def test_un_especialista_no_cambia_parametros(cliente, token_especialista):
    """Leer sí, cambiar no. Son dos permisos distintos."""
    r = cliente.patch(
        "/api/v1/configuracion/parametros/exportacion_vigencia_horas",
        headers=_cab(token_especialista),
        json={"valor": 24, "justificacion": JUSTIFICACION})
    assert r.status_code == 403
    assert r.get_json()["error"]["codigo"] == "SIN_PERMISO"


def test_un_parametro_sin_limites_declarados_no_se_puede_cambiar():
    """Agregar un parámetro nuevo no lo deja modificable por omisión.

    El camino fácil sería permitirlo «porque nadie declaró un límite», y
    entonces un parámetro nuevo quedaría sin protección sin que nadie lo
    hubiera decidido.
    """
    from comun.datos import consultar
    sin_limite = consultar(
        "SELECT p.clave FROM agregado.parametro_privacidad p "
        "  LEFT JOIN configuracion.limite_parametro l USING (clave) "
        " WHERE l.clave IS NULL")
    # Hoy todos tienen límite. Si alguien agrega uno sin límite, esta
    # prueba lo señala en lugar de dejarlo pasar en silencio.
    assert not sin_limite, (
        f"Estos parametros no tienen limites declarados: "
        f"{[f['clave'] for f in sin_limite]}. Hay que declararlos en "
        f"configuracion.limite_parametro o no se podran gobernar.")


# =========================================================================
# Límites por perfil
# =========================================================================

def test_el_auditor_tiene_un_tope_mas_alto_que_el_colaborador(cliente,
                                                              token_admin):
    """Un tope bajo para el auditor no protege nada.

    Revisar una bitácora es, por definición, leer muchos registros.
    """
    r = cliente.get("/api/v1/configuracion/limites-perfil",
                    headers=_cab(token_admin))
    assert r.status_code == 200, r.get_data(as_text=True)
    por_perfil = {(l["perfil"], l["recurso"]): l["maximo_por_hora"]
                  for l in r.get_json()["limites"]}
    assert (por_perfil[("AUDITOR", "consultas")]
            > por_perfil[("COLABORADOR", "consultas")])
    # Y cada tope dice por qué es ese.
    for limite in r.get_json()["limites"]:
        assert len(limite["motivo"]) > 30, limite


def test_mis_limites_no_exige_permiso_especial(cliente, token_colaborador):
    """Un cliente que no sabe su tope reintenta en bucle contra un 429."""
    r = cliente.get("/api/v1/configuracion/mis-limites",
                    headers=_cab(token_colaborador))
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    assert d["limites"]
    assert all(l["maximo_por_hora"] > 0 for l in d["limites"])


def test_sin_token_no_se_ven_los_limites(cliente):
    assert cliente.get("/api/v1/configuracion/mis-limites").status_code == 401


# =========================================================================
# Contrato y sonda
# =========================================================================

def test_el_contrato_cubre_todas_las_rutas(cliente, configuracion):
    contrato = cliente.get("/openapi.json").get_json()
    documentadas = set(contrato["paths"])
    reales = {str(r.rule).replace("<clave>", "{clave}")
              for r in configuracion.app.url_map.iter_rules()
              if "/configuracion" in str(r.rule)}
    faltan = reales - documentadas
    assert not faltan, f"Rutas sin documentar: {faltan}"


def test_los_codigos_de_bitacora_existen_en_la_base():
    from comun.datos import consultar
    import re
    ruta = os.path.join(RAIZ, "apps", "microservicios",
                        "configuration-service", "app.py")
    with open(ruta, encoding="utf-8") as f:
        fuente = f.read()
    usados = set(re.findall(r'_bitacora\("([A-Z_]+)"', fuente))
    declarados = {f["codigo"] for f in consultar(
        "SELECT codigo FROM auditoria.tipo_accion")}
    faltan = usados - declarados
    assert not faltan, (
        f"Codigos sin declarar en auditoria.tipo_accion: {sorted(faltan)}. "
        f"La insercion fallaria en silencio.")


def test_la_sonda_de_salud_declara_sus_dependencias(cliente):
    r = cliente.get("/health/ready")
    assert r.status_code == 200, r.get_data(as_text=True)
    assert set(r.get_json()["dependencias"]) >= {"postgresql", "redis"}
