"""
monitoring-service — salud, latencia y errores de los demás componentes.

LA PRUEBA QUE JUSTIFICA EL ARCHIVO
----------------------------------
Que un componente vigilado esté caído **no** debe poner a este servicio en
`no_listo`.

Es el error obvio al escribir un monitor, y es grave: si monitoring se
declarara no listo porque lo que vigila está caído, el orquestador lo
sacaría de servicio y perderíamos la vista del sistema justo en el momento
en que hace falta mirarla. Un monitor que se apaga cuando hay un incendio
es peor que no tener monitor, porque se confía en él.

Las otras dos que importan:

  · que «degradado» no se confunda con «caído» —se arreglan distinto—, y
  · que un 503 con cuerpo se lea como «contestó y le falta algo», no como
    «no contestó».
"""
import os
import time

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def monitoreo():
    from conftest import _cargar
    modulo = _cargar("monitoring-service", "svc_monitor")
    modulo.app.config["TESTING"] = True
    return modulo


@pytest.fixture
def cliente(monitoreo):
    return monitoreo.app.test_client()


def _cab(token):
    return {"Authorization": f"Bearer {token}"}


def _sondas_falsas(monitoreo, monkeypatch, por_componente, demora=0.0):
    """Sustituye la sonda para fijar el estado de cada componente.

    Hace falta porque en el entorno de pruebas no hay servicios
    escuchando: sin esto, los quince saldrían como `sin_respuesta` y no se
    podría probar ninguno de los otros tres estados, que son justo los que
    el servicio existe para distinguir.
    """
    def falsa(nombre, puerto):
        if demora:
            time.sleep(demora)
        estado = por_componente.get(nombre, "listo")
        return {"componente": nombre, "estado": estado,
                "http": 503 if estado == "no_listo" else 200,
                "latencia_ms": 1.0, "latencia_alta": False,
                "dependencias": {}, "degradado_por": [], "falta": []}

    monkeypatch.setattr(monitoreo, "_sondear", falsa)


# =========================================================================
# La decisión que define al servicio
# =========================================================================

def test_un_componente_caido_no_pone_a_monitoreo_en_no_listo(cliente):
    """En el entorno de pruebas NINGÚN componente responde.

    Es el peor caso posible, y es exactamente el que tiene que soportar:
    los quince vigilados caídos, y su propia sonda en `listo` porque
    PostgreSQL y Redis —sus dependencias de verdad— sí están.
    """
    r = cliente.get("/health/ready")
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    assert d["estado"] == "listo", (
        "Monitoreo se declaro no listo con los vigilados caidos. El "
        "orquestador lo sacaria de servicio justo cuando hace falta verlo.")
    # Y su sonda vigila solo lo suyo: ningún componente vigilado aparece
    # como dependencia propia.
    assert set(d["dependencias"]) == {"postgresql", "redis"}


def test_la_sonda_propia_no_declara_a_los_vigilados(monitoreo):
    """Mirado desde el otro lado: la lista de vigilados no es su lista de
    dependencias, y son más de diez, así que confundirlas sería fácil."""
    vigilados = {n for n, _ in monitoreo.COMPONENTES}
    assert len(vigilados) >= 10
    sonda = monitoreo.app.test_client().get("/health/ready").get_json()
    assert not (vigilados & set(sonda["dependencias"]))


# =========================================================================
# Los cuatro estados, que es todo el valor del panel
# =========================================================================

def test_degradado_no_se_confunde_con_caido(cliente, token_admin, monitoreo,
                                            monkeypatch):
    """Se arreglan distinto, y la sonda devuelve 200 en los dos casos.

    Deducir el estado del código HTTP juntaría «listo» con «degradado»
    justo cuando la diferencia es lo único que importa.
    """
    _sondas_falsas(monitoreo, monkeypatch, {"documents-service": "degradado"})
    r = cliente.get("/api/v1/monitoreo/componentes", headers=_cab(token_admin))
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    assert d["veredicto"] == "degradado", d["por_estado"]
    assert d["por_estado"]["degradado"] == 1
    assert "sin_respuesta" not in d["por_estado"]


def test_un_servicio_sin_respuesta_da_veredicto_con_fallas(cliente,
                                                           token_admin,
                                                           monitoreo,
                                                           monkeypatch):
    """Un degradado no es urgente y un sin_respuesta sí.

    Juntarlos en un semáforo de dos colores haría que se atendieran igual.
    """
    _sondas_falsas(monitoreo, monkeypatch,
                   {"queries-service": "sin_respuesta",
                    "documents-service": "degradado"})
    d = cliente.get("/api/v1/monitoreo/componentes",
                    headers=_cab(token_admin)).get_json()
    assert d["veredicto"] == "con_fallas"
    assert d["por_estado"]["sin_respuesta"] == 1
    assert d["por_estado"]["degradado"] == 1


def test_no_listo_y_sin_respuesta_son_estados_distintos(cliente, token_admin,
                                                        monitoreo, monkeypatch):
    """Uno contestó y dijo qué le falta; el otro no contestó.

    Mezclarlos haría buscar el problema en el lugar equivocado: en el
    primero el servicio está vivo y el problema es su dependencia; en el
    segundo el problema es el servicio.
    """
    _sondas_falsas(monitoreo, monkeypatch,
                   {"reports-service": "no_listo",
                    "trends-service": "sin_respuesta"})
    d = cliente.get("/api/v1/monitoreo/componentes",
                    headers=_cab(token_admin)).get_json()
    por_nombre = {c["componente"]: c for c in d["componentes"]}
    assert por_nombre["reports-service"]["estado"] == "no_listo"
    assert por_nombre["reports-service"]["http"] == 503
    assert por_nombre["trends-service"]["estado"] == "sin_respuesta"
    # El cuerpo explica la diferencia a quien lee el panel.
    assert "no contesto" in d["nota_estados"].lower()


def test_todo_listo_da_operativo(cliente, token_admin, monitoreo, monkeypatch):
    _sondas_falsas(monitoreo, monkeypatch, {})
    d = cliente.get("/api/v1/monitoreo/componentes",
                    headers=_cab(token_admin)).get_json()
    assert d["veredicto"] == "operativo"
    assert d["total"] == len(monitoreo.COMPONENTES)


# =========================================================================
# El sondeo en paralelo
# =========================================================================

def test_las_sondas_van_en_paralelo(monitoreo, monkeypatch):
    """En serie, quince sondas de 2.5 s son más de medio minuto.

    Y con las esperas en serie el peor caso del panel depende de CUÁNTOS
    componentes estén caídos, que es exactamente cuando hay que abrirlo
    rápido. Esta prueba falla si alguien cambia el pool por un bucle.
    """
    demora = 0.3
    _sondas_falsas(monitoreo, monkeypatch, {}, demora=demora)
    inicio = time.perf_counter()
    filas = monitoreo._sondear_todos()
    transcurrido = time.perf_counter() - inicio

    serie = demora * len(monitoreo.COMPONENTES)
    assert len(filas) == len(monitoreo.COMPONENTES)
    assert transcurrido < serie / 3, (
        f"El sondeo tardo {transcurrido:.2f}s; en serie seria {serie:.2f}s. "
        f"Parece que dejo de ir en paralelo.")


# =========================================================================
# Un componente solo
# =========================================================================

def test_un_componente_desconocido_es_404(cliente, token_admin):
    r = cliente.get("/api/v1/monitoreo/componentes/servicio-inventado",
                    headers=_cab(token_admin))
    assert r.status_code == 404
    error = r.get_json()["error"]
    assert error["codigo"] == "COMPONENTE_NO_EXISTE"
    # Dice cuáles sí existen: sin eso el cliente adivina el nombre.
    assert "auth-service" in error["mensaje"]


def test_un_componente_conocido_reporta_la_url_que_sondeo(cliente, token_admin):
    """Sin la URL, un «sin_respuesta» no se puede diagnosticar.

    Si el monitor apunta al puerto equivocado, el síntoma es idéntico a un
    servicio caído.
    """
    r = cliente.get("/api/v1/monitoreo/componentes/auth-service",
                    headers=_cab(token_admin))
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    assert d["componente"] == "auth-service"
    assert d["url_sondeada"].endswith("/health/ready")
    assert d["momento"]


# =========================================================================
# Dependencias compartidas
# =========================================================================

def test_mongodb_caido_no_es_una_falla_del_sistema(cliente, token_admin):
    """Es opcional para los tres componentes que lo usan.

    En este entorno MongoDB no está instalado, así que la prueba recorre
    justamente el caso que importa: el veredicto no puede ser `con_fallas`
    solo porque una dependencia opcional no esté.
    """
    r = cliente.get("/api/v1/monitoreo/dependencias", headers=_cab(token_admin))
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    assert d["dependencias"]["postgresql"]["ok"] is True
    assert d["dependencias"]["redis"]["ok"] is True
    assert d["esenciales_caidas"] == []
    assert d["veredicto"] in ("operativo", "degradado")
    assert d["veredicto"] != "con_fallas", (
        "Con las dos esenciales arriba, el veredicto no puede ser "
        "con_fallas aunque MongoDB no responda: es opcional.")


# =========================================================================
# Errores recientes
# =========================================================================

def test_los_errores_salen_de_la_bitacora_no_de_un_contador(cliente,
                                                            token_auditor):
    """Un contador en memoria se pierde al reiniciar el proceso.

    Que es justo lo que pasa cuando algo va mal: el dato desaparecería en
    el momento en que hacía falta.
    """
    r = cliente.get("/api/v1/monitoreo/errores?horas=24",
                    headers=_cab(token_auditor))
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    assert d["ventana_horas"] == 24
    assert isinstance(d["por_accion_y_resultado"], list)
    # La nota evita la lectura equivocada del panel.
    assert "rechazo no es una falla" in d["nota"].lower().replace("  ", " ")


def test_un_rango_de_horas_imposible_se_rechaza(cliente, token_auditor):
    for horas in ("0", "999", "no-es-numero"):
        r = cliente.get(f"/api/v1/monitoreo/errores?horas={horas}",
                        headers=_cab(token_auditor))
        assert r.status_code == 400, (horas, r.get_data(as_text=True))
        assert r.get_json()["error"]["codigo"] == "PARAMETRO_INVALIDO"


# =========================================================================
# Nada de esto es público
# =========================================================================

def test_el_panel_exige_token(cliente):
    """Un panel de monitoreo es lo primero que se abre sin autenticación
    «porque solo son métricas». Aquí eso sería una fuga: saber que una
    unidad tiene datos publicados ya dice algo de esa unidad."""
    for ruta in ("/api/v1/monitoreo/componentes",
                 "/api/v1/monitoreo/componentes/auth-service",
                 "/api/v1/monitoreo/dependencias",
                 "/api/v1/monitoreo/errores"):
        r = cliente.get(ruta)
        assert r.status_code == 401, (ruta, r.status_code)


def test_los_errores_exigen_permiso_de_bitacora(cliente, token_colaborador):
    """Aunque solo sean conteos: un conteo de rechazos por unidad ya dice
    en qué unidad está pasando algo."""
    r = cliente.get("/api/v1/monitoreo/errores", headers=_cab(token_colaborador))
    assert r.status_code == 403
    assert r.get_json()["error"]["codigo"] == "SIN_PERMISO"


def test_el_panel_no_devuelve_ningun_dato_de_personas(cliente, token_admin,
                                                      monitoreo, monkeypatch):
    """El panel es estado operativo y nada más.

    Se comprueba sobre el texto crudo de la respuesta porque lo que
    importa es que no salga, no por qué camino podría salir.
    """
    _sondas_falsas(monitoreo, monkeypatch, {})
    texto = cliente.get("/api/v1/monitoreo/componentes",
                        headers=_cab(token_admin)).get_data(as_text=True)
    for prohibido in ("@nexum.com.mx", "empleado", "seudonimo",
                      "valor_protegido", "autoreporte"):
        assert prohibido not in texto, prohibido


# =========================================================================
# Contrato
# =========================================================================

def test_el_contrato_cubre_todas_las_rutas(cliente, monitoreo):
    contrato = cliente.get("/openapi.json").get_json()
    documentadas = set(contrato["paths"])
    reales = {str(r.rule).replace("<nombre>", "{nombre}")
              for r in monitoreo.app.url_map.iter_rules()
              if "/monitoreo" in str(r.rule)}
    faltan = reales - documentadas
    assert not faltan, f"Rutas sin documentar: {faltan}"


# =========================================================================
# Supervisión de contenedores
# =========================================================================
# LA PRUEBA QUE JUSTIFICA ESTA PARTE
# ----------------------------------
# Un contenedor en bucle de reinicio pasa TODAS las sondas de salud,
# porque cada sonda le llega a un proceso recién arrancado que contesta
# «vivo» con toda honestidad. Esta es la única vista del proyecto donde
# ese problema se ve, así que es la única que puede comprobarlo.

def _vidas_falsas(monitoreo, monkeypatch, por_componente):
    """Fija la respuesta de `/health/live` de cada componente.

    Hace falta porque en el entorno de pruebas no hay servicios
    escuchando: sin esto, los dieciséis saldrían como «no responde» y no
    se podría probar la detección de reinicios, que es lo único que
    importa aquí.
    """
    def falsa(nombre, puerto):
        return por_componente.get(nombre)
    monkeypatch.setattr(monitoreo, "_vida_de", falsa)


def _limpiar_estado(monitoreo):
    """Borra lo que este servicio recuerda de instancias y reinicios.

    Las pruebas tienen que partir de cero: si no, la segunda corrida de la
    suite vería los reinicios que simuló la primera y contaría de más.
    """
    from comun import obtener_redis
    r = obtener_redis()
    r.delete(monitoreo.CLAVE_INSTANCIAS)
    for nombre, _ in monitoreo.COMPONENTES:
        r.delete(f"{monitoreo.CLAVE_REINICIOS}:{nombre}")


def test_un_reinicio_se_detecta_porque_cambia_la_instancia(
        cliente, token_admin, monitoreo, monkeypatch):
    """La primera visita no es un reinicio; la segunda con otra instancia sí.

    Que la primera NO cuente importa: si contara, cada arranque de
    monitoring-service reportaría los dieciséis componentes como
    reiniciados y la vista sería inútil desde el primer minuto.
    """
    _limpiar_estado(monitoreo)
    vida = {"servicio": "queries-service", "instancia": "aaa111",
            "arrancado_en": "2026-11-05T10:00:00+00:00",
            "segundos_arriba": 3600}
    _vidas_falsas(monitoreo, monkeypatch, {"queries-service": vida})

    primera = cliente.get("/api/v1/monitoreo/contenedores",
                          headers=_cab(token_admin)).get_json()
    fila = next(c for c in primera["componentes"]
                if c["componente"] == "queries-service")
    assert fila["reinicio_desde_la_ultima_revision"] is False, (
        "La primera vez que se ve un componente no es un reinicio.")
    assert fila["reinicios_en_la_ventana"] == 0

    # Mismo componente, otra instancia: el proceso es nuevo.
    vida["instancia"] = "bbb222"
    segunda = cliente.get("/api/v1/monitoreo/contenedores",
                          headers=_cab(token_admin)).get_json()
    fila = next(c for c in segunda["componentes"]
                if c["componente"] == "queries-service")
    assert fila["reinicio_desde_la_ultima_revision"] is True
    assert fila["reinicios_en_la_ventana"] == 1


def test_un_bucle_de_reinicios_se_marca(cliente, token_admin, monitoreo,
                                        monkeypatch):
    """Y las sondas de salud siguen diciendo que todo está bien.

    Esa es la frase que resume por qué existe este endpoint.
    """
    _limpiar_estado(monitoreo)
    vida = {"servicio": "reports-service", "instancia": "i0",
            "arrancado_en": "2026-11-05T10:00:00+00:00",
            "segundos_arriba": 4}
    _vidas_falsas(monitoreo, monkeypatch, {"reports-service": vida})

    for n in range(monitoreo.REINICIOS_EN_BUCLE + 1):
        vida["instancia"] = f"i{n}"
        d = cliente.get("/api/v1/monitoreo/contenedores",
                        headers=_cab(token_admin)).get_json()

    fila = next(c for c in d["componentes"]
                if c["componente"] == "reports-service")
    assert fila["en_bucle"] is True, fila
    assert "reports-service" in d["en_bucle"]
    assert "no ven esto" in fila["nota"].lower()


def test_un_servicio_sin_identidad_de_instancia_no_se_da_por_estable(
        cliente, token_admin, monitoreo, monkeypatch):
    """Decir «sin reinicios» sería afirmar algo que no se comprobó."""
    _limpiar_estado(monitoreo)
    _vidas_falsas(monitoreo, monkeypatch, {
        "catalog-service": {"servicio": "catalog-service", "estado": "vivo"}})
    d = cliente.get("/api/v1/monitoreo/contenedores",
                    headers=_cab(token_admin)).get_json()
    fila = next(c for c in d["componentes"]
                if c["componente"] == "catalog-service")
    assert fila["supervision"] == "NO_DISPONIBLE"
    assert "reinicio_desde_la_ultima_revision" not in fila
    assert "no significa que no lo haya hecho" in fila["nota"].lower()


def test_el_reinicio_queda_en_la_bitacora(cliente, token_admin, monitoreo,
                                          monkeypatch):
    """Redis recorta su ventana; la bitácora es el único rastro que queda.

    Y el INSERT va envuelto en un try para no tumbar la petición, así que
    si el código de acción no estuviera declarado en la base fallaría EN
    SILENCIO: la vista funcionaría en pantalla y no guardaría nada. Es el
    mismo error que costó todos los rechazos de permiso antes de la
    migración 007.
    """
    _limpiar_estado(monitoreo)
    from comun.datos import consultar_uno
    antes = consultar_uno(
        "SELECT count(*) AS n FROM auditoria.bitacora "
        " WHERE accion = 'COMPONENTE_REINICIADO'")["n"]

    vida = {"servicio": "trends-service", "instancia": "x1",
            "arrancado_en": "2026-11-05T10:00:00+00:00",
            "segundos_arriba": 10}
    _vidas_falsas(monitoreo, monkeypatch, {"trends-service": vida})
    cliente.get("/api/v1/monitoreo/contenedores", headers=_cab(token_admin))
    vida["instancia"] = "x2"
    cliente.get("/api/v1/monitoreo/contenedores", headers=_cab(token_admin))

    despues = consultar_uno(
        "SELECT count(*) AS n FROM auditoria.bitacora "
        " WHERE accion = 'COMPONENTE_REINICIADO'")["n"]
    assert despues == antes + 1, (
        "El reinicio no quedo en la bitacora. Si el codigo "
        "COMPONENTE_REINICIADO no esta en auditoria.tipo_accion, el INSERT "
        "falla por llave foranea y el try se lo traga: la vista funciona en "
        "pantalla y no guarda nada.")


def test_no_se_lee_el_socket_de_docker(monitoreo):
    """Montarlo daria control del demonio, y eso es root en la maquina.

    Se comprueba sobre el código y no sobre el comportamiento porque lo
    que importa es que nadie lo agregue después «porque es más fácil».
    """
    ruta = os.path.join(RAIZ, "apps", "microservicios",
                        "monitoring-service", "app.py")
    with open(ruta, encoding="utf-8") as f:
        lineas = f.read().splitlines()

    # Se miran solo las líneas de CÓDIGO. La primera versión de esta prueba
    # fallaba por el comentario que explica justamente por qué no se usa el
    # socket: una prueba que castiga la explicación de una decisión empuja
    # a borrar la explicación, que es lo contrario de lo que hace falta.
    codigo = "\n".join(l for l in lineas if not l.strip().startswith("#"))
    for prohibido in ("docker.sock", "docker_sock", "from docker import",
                      "import docker", "docker ps"):
        assert prohibido not in codigo, (
            f"'{prohibido}' aparece en el codigo. Montar el socket de Docker "
            f"en un contenedor le da control del demonio, y con eso puede "
            f"arrancar otro contenedor con el sistema de archivos del "
            f"anfitrion montado: equivale a root en la maquina.")
    # Y el motivo está publicado, no solo respetado.
    cliente = monitoreo.app.test_client()
    contrato = cliente.get("/openapi.json").get_json()
    texto = contrato["paths"]["/api/v1/monitoreo/contenedores"]["get"]["description"]
    assert "socket de Docker" in texto


# =========================================================================
# Alertas
# =========================================================================

def test_un_componente_caido_genera_una_alerta_critica(cliente, token_admin,
                                                       monitoreo, monkeypatch):
    _sondas_falsas(monitoreo, monkeypatch,
                   {"queries-service": "sin_respuesta"})
    d = cliente.get("/api/v1/monitoreo/alertas",
                    headers=_cab(token_admin)).get_json()
    criticas = [a for a in d["alertas"] if a["severidad"] == "CRITICA"]
    assert any(a["regla"] == "COMPONENTE_SIN_RESPUESTA" and
               a["componente"] == "queries-service" for a in criticas), d
    # Cada alerta trae qué hacer: una que solo dice «algo va mal» obliga a
    # reconstruir el diagnóstico cada vez.
    for alerta in d["alertas"]:
        assert alerta["accion"], alerta
        assert alerta["evidencia"], alerta


def test_las_alertas_vienen_ordenadas_por_severidad(cliente, token_admin,
                                                    monitoreo, monkeypatch):
    """Quien abre el panel en una caída lee la primera, no las veinte."""
    _sondas_falsas(monitoreo, monkeypatch,
                   {"queries-service": "sin_respuesta",
                    "documents-service": "degradado",
                    "reports-service": "no_listo"})
    d = cliente.get("/api/v1/monitoreo/alertas",
                    headers=_cab(token_admin)).get_json()
    orden = {s: i for i, s in enumerate(monitoreo.SEVERIDADES)}
    valores = [orden[a["severidad"]] for a in d["alertas"]]
    assert valores == sorted(valores), [a["severidad"] for a in d["alertas"]]


def test_un_degradado_no_se_reporta_como_falla(cliente, token_admin,
                                               monitoreo, monkeypatch):
    """Es un servicio atendiendo sin una dependencia opcional.

    Si saliera como CRITICA, se atendería con la misma urgencia que una
    caída y el panel dejaría de servir para priorizar.
    """
    _sondas_falsas(monitoreo, monkeypatch, {"documents-service": "degradado"})
    d = cliente.get("/api/v1/monitoreo/alertas",
                    headers=_cab(token_admin)).get_json()
    alerta = next(a for a in d["alertas"]
                  if a["regla"] == "COMPONENTE_DEGRADADO")
    assert alerta["severidad"] == "MEDIA"
    assert "no es urgente" in alerta["accion"].lower()


def test_el_presupuesto_de_privacidad_es_una_regla_de_alerta(cliente,
                                                             token_admin,
                                                             monitoreo,
                                                             monkeypatch):
    """Es la alerta más propia de este sistema.

    Cuando el épsilon de una campaña se agota, la unidad deja de poder
    publicar. Todo responde, nada falla, y para quien opera se ve como
    «ya no salen datos nuevos»: sin la alerta se busca el problema en el
    lugar equivocado.
    """
    _sondas_falsas(monitoreo, monkeypatch, {})
    d = cliente.get("/api/v1/monitoreo/alertas",
                    headers=_cab(token_admin)).get_json()
    assert "PRESUPUESTO_AGOTADO" in d["reglas_evaluadas"]
    assert "PRESUPUESTO_POR_AGOTARSE" in d["reglas_evaluadas"]
    for alerta in d["alertas"]:
        if alerta["regla"].startswith("PRESUPUESTO"):
            # No se presenta como error: es la privacidad funcionando.
            assert "no se sube callando" in alerta["accion"].lower() or \
                   "antes de que se agote" in alerta["accion"].lower()


def test_el_servicio_dice_que_no_entrega_las_alertas(cliente, token_admin,
                                                     monitoreo, monkeypatch):
    """Un monitor cuyo envío falla en silencio es peor que no tenerlo.

    Que lo diga en la respuesta evita la lectura más peligrosa: creer que
    alguien va a recibir un correo cuando nadie lo va a recibir.
    """
    _sondas_falsas(monitoreo, monkeypatch, {})
    d = cliente.get("/api/v1/monitoreo/alertas",
                    headers=_cab(token_admin)).get_json()
    assert "notifications-service" in d["quien_las_entrega"]
    assert "publica" in d["quien_las_entrega"].lower()


def test_las_vistas_nuevas_exigen_token(cliente):
    for ruta in ("/api/v1/monitoreo/contenedores",
                 "/api/v1/monitoreo/alertas"):
        assert cliente.get(ruta).status_code == 401, ruta
