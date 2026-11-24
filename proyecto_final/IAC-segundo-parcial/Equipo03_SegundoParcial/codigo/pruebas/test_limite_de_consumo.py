"""
El límite de consumo, probado a propósito.

El contrato de los ocho servicios declara un 429 y una cabecera
Retry-After. Declararlo y no probarlo es lo mismo que no tenerlo: el límite
vive en Redis con una ventana deslizante, y es fácil que un refactor lo
deje contando por servicio en lugar de por usuario, o que la cabecera
desaparezca sin que nada falle.

Esta prueba apaga la limpieza automática de contadores (ver conftest) para
poder agotar la cuota de verdad.
"""
import os

import pytest
import redis as _redis
from conftest import cab


@pytest.fixture
def sin_limite_acumulado():
    """Anula la fixture global: aquí el contador NO se limpia."""
    yield


def _contadores_del_usuario():
    r = _redis.Redis(host=os.environ["REDIS_HOST"], port=6379,
                     decode_responses=True)
    return {c: r.get(c) for c in r.scan_iter("limite:*", count=1000)}


def test_el_limite_responde_429_y_dice_cuanto_esperar(reportes, token_admin):
    """Se agota la cuota de POST /reportes, que es de 30 por minuto."""
    r = _redis.Redis(host=os.environ["REDIS_HOST"], port=6379,
                     decode_responses=True)
    for c in list(r.scan_iter("limite:*", count=1000)):
        r.delete(c)

    codigos = []
    for _ in range(34):
        respuesta = reportes.post("/api/v1/reportes", headers=cab(token_admin),
                                  json={"tipo": "PARTICIPACION"})
        codigos.append(respuesta.status_code)
        if respuesta.status_code == 429:
            cuerpo = respuesta.get_json()
            assert cuerpo["error"]["codigo"] == "LIMITE_EXCEDIDO"
            # Sin Retry-After el cliente no sabe si reintentar en un
            # segundo o en una hora, y lo que hace es reintentar en bucle.
            assert "Retry-After" in respuesta.headers
            assert int(respuesta.headers["Retry-After"]) > 0
            break

    assert 429 in codigos, (
        "no se alcanzo el limite en 34 peticiones: el contador no esta "
        f"funcionando. Codigos: {sorted(set(codigos))}")
    assert codigos.count(201) >= 25, (
        "el limite salto demasiado pronto: la cuota declarada es de 30 por "
        f"minuto y solo pasaron {codigos.count(201)}")


def test_el_limite_es_por_usuario_y_no_global(reportes, token_admin,
                                              token_especialista):
    """Un cliente que abusa no puede dejar fuera a los demás.

    Es la propiedad que hace que el límite sea aceptable: si fuera global,
    un script mal hecho de un integrante tumbaría la demostración para
    todos.
    """
    r = _redis.Redis(host=os.environ["REDIS_HOST"], port=6379,
                     decode_responses=True)
    for c in list(r.scan_iter("limite:*", count=1000)):
        r.delete(c)

    # El administrador agota su cuota.
    for _ in range(34):
        if reportes.post("/api/v1/reportes", headers=cab(token_admin),
                         json={"tipo": "PARTICIPACION"}).status_code == 429:
            break

    # Y el especialista, con su propio token, sigue entrando por la MISMA
    # ruta limitada. Tiene que ser la misma ruta: si se probara con una que
    # no lleva limite, la prueba pasaria aunque el contador fuera global.
    otra = reportes.post("/api/v1/reportes", headers=cab(token_especialista),
                         json={"tipo": "TABLERO_CAMPANIA",
                               "parametro": "CAMP-2026-S1"})
    assert otra.status_code == 201, (
        "el limite esta contando por servicio y no por usuario: un cliente "
        f"que abusa deja fuera a todos los demas ({otra.status_code})")

    # Las claves lo confirman: hay una por usuario, no una sola.
    claves = _contadores_del_usuario()
    assert len(claves) >= 2, claves
