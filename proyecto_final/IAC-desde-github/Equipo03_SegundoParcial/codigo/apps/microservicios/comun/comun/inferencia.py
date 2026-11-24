"""
Control de consultas repetidas y de ataques por diferencia.

POR QUÉ ESTE MÓDULO EXISTE
--------------------------
El proyecto afirma que ningún resultado permite llegar a una persona. Esa
afirmación la sostenían hasta ahora dos mecanismos: el umbral k, que impide
publicar un agregado de un grupo pequeño, y el ruido de Laplace, que impide
leer el valor exacto de los que sí se publican.

Los dos miran UNA consulta a la vez, y ahí estaba el hueco: hay información
que ninguna consulta revela por separado y que la COMBINACIÓN de dos sí
revela.

    El agregado de Operaciones se publicó con 120 respondientes. El de
    Call Center Turno A, con 116. Los dos pasan el umbral k, así que los
    dos se publican. Si un líder consulta las dos cifras y resta, obtiene
    el agregado de los 4 respondientes restantes — un grupo que NADIE
    autorizó a publicar, y que está por debajo del umbral.

El residuo se mide en RESPONDIENTES y no en plantilla declarada, porque es
lo que un atacante puede despejar: lo que entra en el valor publicado del
padre y no en el de las hijas que ya tiene. La plantilla no participa en la
decisión de publicar —`fn_calcular_agregado_protegido` cuenta respuestas
distintas— y un control que restara plantillas fallaría en las dos
direcciones. Está explicado en `_comprobar_residuo`, con el defecto que
tenía la primera versión.

Llevado al extremo, si alguien consulta una unidad y después la misma
unidad menos una persona (porque alguien cambió de área entre campañas),
la diferencia es esa persona. Eso es un ataque por diferencia, y es el
modo habitual de romper un sistema de datos agregados que por lo demás
está bien construido.

QUÉ HACE Y QUÉ NO HACE
----------------------
Hace dos cosas, y conviene no confundirlas:

1. `registrar_consulta` lleva la cuenta de qué unidades ha consultado cada
   actor en una ventana de tiempo, en Redis.

2. `verificar_diferencia` revisa, ANTES de responder, si la unidad pedida
   combinada con las que ese actor ya consultó deja un residuo menor que k.
   Si lo deja, no responde.

Lo que NO hace es volver a aplicar ruido en cada lectura. En este sistema
el ruido se aplica UNA vez, al publicar, y se guarda; repetir la consulta
devuelve el mismo valor. Esa decisión ya protege del ataque por promedio
—pedir mil veces y promediar para cancelar el ruido—, porque no hay mil
valores distintos que promediar, hay uno. Volver a ruidificar en cada
lectura sería un error caro: abriría justo ese ataque.

Por eso el «control de consultas repetidas» de aquí no es un límite de
velocidad (ese ya existe aparte, en `limite_consumo`). Es un registro: una
repetición anormal no rompe nada por sí sola, pero describe a alguien que
está explorando, y de eso tiene que quedar rastro.

LÍMITES CONOCIDOS
-----------------
Con los datos sembrados hoy este control no bloquea nada, y conviene
decirlo en lugar de presentarlo como una defensa en funcionamiento:
ninguna unidad publicada es padre de otra, porque solo se agregan las
hojas del árbol. Sin un agregado de nivel superior publicado no hay
minuendo que restar. El control existe para el momento en que eso cambie
—basta publicar un agregado por área para que el ataque sea posible— y
una demostración que enseñara un bloqueo con estos datos estaría
enseñando el bloqueo de una consulta inofensiva, no una fuga evitada.

La ventana es por actor. Dos personas coordinadas, o la misma persona con
dos cuentas, pueden repartirse las consultas y quedar por debajo del
umbral. Cerrar eso exige llevar el estado por unidad y no por actor, lo que
convierte cualquier consulta de una unidad grande en un bloqueo para todos
los demás. Se eligió el falso negativo sobre el falso positivo, a
conciencia, y queda dicho aquí para que quien lo lea sepa qué compró.
"""
import json
import time

from .errores import ErrorApi

# Ventana de observación. Media hora: lo bastante larga para cubrir una
# sesión de trabajo real y lo bastante corta para que el estado no crezca
# sin control ni castigue a quien vuelve al día siguiente.
VENTANA_SEGUNDOS = 1800

# A partir de cuántas repeticiones del MISMO recurso con los MISMOS
# parámetros se considera anormal. Diez permite recargar una pantalla con
# soltura; cincuenta describe a alguien raspando.
REPETICIONES_ANORMALES = 25


def _clave_actor(actor_id, sufijo):
    return f"inferencia:{sufijo}:{actor_id}"


def registrar_consulta(redis, actor_id, recurso, parametros):
    """Anota la consulta y devuelve cuántas veces se repitió en la ventana.

    Devuelve 0 si Redis no responde. La ausencia del registro NO debe
    impedir la consulta: este control detecta exploración, no protege de
    una fuga inmediata, y negar el servicio por una caída de la caché
    sería un remedio peor que la enfermedad.
    """
    if not actor_id:
        return 0
    firma = json.dumps({"r": recurso, "p": parametros}, sort_keys=True,
                       ensure_ascii=False, default=str)
    clave = _clave_actor(actor_id, "repeticion")
    try:
        n = redis.hincrby(clave, firma, 1)
        redis.expire(clave, VENTANA_SEGUNDOS)
        return int(n)
    except Exception:
        return 0


def registrar_unidad(redis, actor_id, unidad_id):
    """Recuerda que este actor ya obtuvo el agregado de esta unidad."""
    if not actor_id or not unidad_id:
        return
    clave = _clave_actor(actor_id, "unidades")
    try:
        redis.sadd(clave, unidad_id)
        redis.expire(clave, VENTANA_SEGUNDOS)
    except Exception:
        pass


def unidades_consultadas(redis, actor_id):
    if not actor_id:
        return set()
    try:
        crudas = redis.smembers(_clave_actor(actor_id, "unidades"))
    except Exception:
        return set()
    return {u.decode() if isinstance(u, bytes) else str(u) for u in crudas}


def verificar_diferencia(redis, actor_id, unidad_id, consultar_uno, k_minimo):
    """Niega la consulta si, combinada con las previas, aísla un grupo < k.

    Revisa las dos direcciones del árbol, porque el ataque funciona igual
    en las dos:

      · hacia abajo: el actor ya tiene la unidad PADRE y ahora pide una
        hija. Residuo = padre − (hijas que ya tiene + la que pide).
      · hacia arriba: el actor ya tiene hijas y ahora pide el padre.
        Mismo residuo, descubierto en el otro orden.

    El residuo se mide en RESPONDIENTES, no en plantilla declarada. Ver
    `_comprobar_residuo`: el primer intento usaba la plantilla y era
    incorrecto en las dos direcciones.
    """
    if not actor_id or not unidad_id:
        return

    fila = consultar_uno(
        "SELECT unidad_organizacional_id, unidad_padre_id "
        "  FROM organizacion.unidad_organizacional "
        " WHERE unidad_organizacional_id = %s", (unidad_id,))
    if not fila:
        return

    previas = unidades_consultadas(redis, actor_id)
    if not previas:
        return

    padre_id = fila.get("unidad_padre_id")

    # --- caso 1: ya tiene el padre, ahora pide una hija -----------------
    if padre_id and padre_id in previas:
        _comprobar_residuo(consultar_uno, padre_id, previas | {unidad_id},
                           k_minimo, unidad_id)

    # --- caso 2: ahora pide el padre y ya tiene hijas -------------------
    hijas_previas = consultar_uno(
        "SELECT count(*) AS n FROM organizacion.unidad_organizacional "
        " WHERE unidad_padre_id = %s AND unidad_organizacional_id = ANY(%s)",
        (unidad_id, list(previas))) or {}
    if hijas_previas.get("n", 0) > 0:
        _comprobar_residuo(consultar_uno, unidad_id, previas | {unidad_id},
                           k_minimo, unidad_id)


def _comprobar_residuo(consultar_uno, padre_id, conocidas, k_minimo, pedida):
    """Residuo = RESPONDIENTES del padre − respondientes de las hijas.

    POR QUÉ RESPONDIENTES Y NO PLANTILLA DECLARADA
    ----------------------------------------------
    El primer intento de esta función restaba `plantilla_declarada`, y el
    comentario que lo acompañaba afirmaba que la plantilla es «el mismo
    dato que usa el umbral k al publicar». Es falso:
    `agregado.fn_calcular_agregado_protegido` cuenta
    `COUNT(DISTINCT respuesta_id)` y suprime cuando ESE número queda bajo
    k. La plantilla no entra en la decisión de publicar.

    La diferencia no es de precisión, y falla en las dos direcciones:

      · Permisiva, que es la peligrosa. Una unidad con 200 de plantilla y
        6 respondientes deja un residuo de plantilla grande —el control
        dice que pase— mientras el residuo de respondientes puede ser de
        dos personas. El ataque funciona y el control dijo que sí.

      · Restrictiva. Un residuo de plantilla de 3 personas que no
        respondieron no permite deducir nada, porque no hay valor suyo
        dentro del agregado del padre. El control negaba una consulta que
        no podía filtrar nada.

    Lo que un atacante puede despejar por resta son los RESPONDIENTES que
    están dentro del valor publicado del padre y no dentro de los valores
    publicados de las hijas que ya tiene. Eso es lo que se mide aquí.

    SOLO DONDE EL PADRE ESTÁ PUBLICADO
    ----------------------------------
    Si el padre no tiene valor publicado para una campaña y dimensión, no
    hay minuendo: no hay nada que restar y no hay nada que bloquear. Por
    eso la consulta arranca de `agregado.resultado_protegido` del padre y
    no del árbol de unidades.

    Conviene decir con qué datos corre esto hoy: en la base sembrada
    NINGUNA unidad publicada es padre de otra —solo se agregan las hojas—,
    así que este control no tiene nada que bloquear con los datos
    actuales. No es decorativo: basta que alguien publique un agregado de
    un nivel superior para que el ataque se vuelva posible, y entonces el
    control ya está puesto. Pero una demostración que enseñe un bloqueo
    con estos datos estaría enseñando el bloqueo de una consulta
    inofensiva, no una fuga evitada.
    """
    hijas = sorted(set(conocidas) - {padre_id})
    if not hijas:
        return

    # Se busca el residuo OFENSIVO MÁS PEQUEÑO entre todas las parejas
    # (campaña, dimensión) en que el padre está publicado. Basta una para
    # negar: el atacante elige la que le sirva.
    peor = consultar_uno(
        "SELECT t.campania_id, t.dimension_id, t.residuo FROM ("
        "  SELECT p.campania_id, p.dimension_id,"
        "         p.n_observaciones"
        "           - coalesce(sum(h.n_observaciones), 0) AS residuo"
        "    FROM agregado.resultado_protegido p"
        "    LEFT JOIN agregado.resultado_protegido h"
        "           ON h.campania_id = p.campania_id"
        "          AND coalesce(h.dimension_id, '') = coalesce(p.dimension_id, '')"
        "          AND h.unidad_organizacional_id = ANY(%s)"
        "          AND h.valor_protegido IS NOT NULL"
        "   WHERE p.unidad_organizacional_id = %s"
        "     AND p.valor_protegido IS NOT NULL"
        "   GROUP BY p.campania_id, p.dimension_id, p.n_observaciones"
        ") t"
        " WHERE t.residuo > 0 AND t.residuo < %s"
        " ORDER BY t.residuo LIMIT 1",
        (list(hijas), padre_id, k_minimo))

    # Un residuo de 0 significa que las hijas cubren al padre completo: no
    # queda nadie aislado. El problema es el residuo PEQUEÑO PERO
    # POSITIVO: ahí queda un grupo que nadie autorizó a publicar.
    if not peor:
        return

    residuo = peor["residuo"]
    raise ErrorApi(
        "INFERENCIA_BLOQUEADA",
        f"Esta consulta no se puede responder. Combinada con las que ya "
        f"hiciste, permitiria despejar por resta el agregado de "
        f"{residuo} respondiente(s) en {peor['campania_id']}, por debajo "
        f"del umbral minimo de {k_minimo}. No es un limite de velocidad: "
        f"responder esta consulta en particular dejaria deducir el "
        f"agregado de un grupo que nadie autorizo a publicar.",
        403,
        [{"campo": "unidad_organizacional_id", "problema": pedida},
         {"campo": "residuo_respondientes", "problema": str(residuo)},
         {"campo": "campania", "problema": str(peor["campania_id"])},
         {"campo": "umbral_k", "problema": str(k_minimo)}])


def verificar_conjunto(unidades, consultar_uno, k):
    """Niega un CONJUNTO de unidades que, entre ellas, aísle un grupo < k.

    POR QUÉ NO BASTA `verificar_diferencia`
    ---------------------------------------
    Esa función lleva el estado de lo que un actor ya consultó, en Redis, y
    revisa la unidad nueva contra ese estado. Funciona para una pantalla:
    cada consulta llega sola y el control decide una por una.

    Un archivo exportado no llega una por una. Lleva todas las unidades
    dentro, y quien lo recibe puede sumar y restar sin volver a pedirle
    nada al sistema: fuera de aquí no hay ventana, ni actor, ni Redis, ni
    control ninguno. Un archivo con «Operaciones» y con tres de sus cuatro
    hijas contiene la cuarta por resta, aunque esa cuarta nunca se haya
    publicado y aunque las cuatro consultas, hechas una a una, se hubieran
    bloqueado.

    De ahí que el control del archivo tenga que mirar el conjunto COMPLETO
    de una vez y antes de escribir nada. Comparte el cálculo del residuo
    con `verificar_diferencia` a propósito: si el archivo usara otro
    criterio que la pantalla, lo que una niega la otra lo entregaría.
    """
    conjunto = {u for u in (unidades or []) if u}
    if len(conjunto) < 2:
        return
    for posible_padre in sorted(conjunto):
        hijas = consultar_uno(
            "SELECT count(*) AS n FROM organizacion.unidad_organizacional "
            " WHERE unidad_padre_id = %s AND unidad_organizacional_id = ANY(%s)",
            (posible_padre, list(conjunto))) or {}
        if hijas.get("n", 0) > 0:
            _comprobar_residuo(consultar_uno, posible_padre, conjunto, k,
                               posible_padre)


def k_minimo(consultar_uno, por_omision=5):
    """Lee el umbral k de la base. Es el MISMO que usa la publicación."""
    fila = consultar_uno(
        "SELECT agregado.fn_parametro('k_umbral_minimo') AS k")
    try:
        return int(float((fila or {}).get("k") or por_omision))
    except (TypeError, ValueError):
        return por_omision
