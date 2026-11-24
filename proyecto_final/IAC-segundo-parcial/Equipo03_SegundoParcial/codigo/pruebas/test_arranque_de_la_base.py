"""
Que una base recién creada quede COMPLETA, por todas las vías de arranque.

POR QUÉ ESTE ARCHIVO EXISTE
---------------------------
Es el error que más veces se repitió en el proyecto y el más difícil de
notar: los archivos de compose y el guión de arranque montaban una lista de
migraciones escrita a mano, y al agregar una migración nadie se acordaba de
actualizar las cuatro listas.

El efecto era desconcertante. La base levantaba, PostgreSQL contestaba su
sonda de salud, el sistema arrancaba — y fallaba al primer uso real con un
error de tabla o de llave foránea. «Levanta bien» y «funciona» no eran lo
mismo, y la sonda decía lo primero.

Peor todavía en el caso de la bitácora: `auditoria.bitacora` tiene una
llave foránea contra `auditoria.tipo_accion`. Sin la migración que agrega
los códigos nuevos, los registros de bitácora fallaban al insertarse, y
como el registro en bitácora está envuelto en un try para que no tumbe la
operación principal, fallaban EN SILENCIO. El sistema parecía funcionar y
no estaba registrando nada.

Estas pruebas no necesitan Docker: leen los archivos.
"""
import os
import re

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIGRACIONES = os.path.join(RAIZ, "db", "migraciones")
SEMILLAS = os.path.join(RAIZ, "db", "semilla")

COMPOSES = [
    os.path.join(RAIZ, "docker-compose.yml"),
    os.path.join(RAIZ, "infra", "compose", "docker-compose.base.yml"),
]


def archivos_de(carpeta, extension=".sql"):
    if not os.path.isdir(carpeta):
        pytest.skip(f"no existe {carpeta}")
    return sorted(a for a in os.listdir(carpeta) if a.endswith(extension))


@pytest.mark.parametrize("compose", COMPOSES, ids=lambda p: os.path.basename(p))
def test_el_compose_monta_todas_las_migraciones(compose):
    if not os.path.exists(compose):
        pytest.skip(f"no existe {compose}")
    texto = open(compose, encoding="utf-8").read()
    faltan = [m for m in archivos_de(MIGRACIONES) if m not in texto]
    assert not faltan, (
        f"{os.path.basename(compose)} no monta estas migraciones: {faltan}. "
        f"Una base creada con este archivo levanta y falla al primer uso "
        f"real; la sonda de salud no lo detecta.")


@pytest.mark.parametrize("compose", COMPOSES, ids=lambda p: os.path.basename(p))
def test_los_permisos_van_despues_de_las_migraciones(compose):
    """09_permisos.sh otorga privilegios sobre objetos que crea la 004."""
    if not os.path.exists(compose):
        pytest.skip(f"no existe {compose}")
    texto = open(compose, encoding="utf-8").read()
    if "09_permisos.sh" not in texto:
        pytest.skip("este compose no monta el script de permisos")
    posicion_permisos = texto.index("09_permisos.sh")
    for migracion in archivos_de(MIGRACIONES):
        if migracion in texto:
            assert texto.index(migracion) < posicion_permisos, (
                f"{migracion} se monta DESPUÉS de 09_permisos.sh. El script "
                f"de permisos otorga privilegios sobre objetos que crean las "
                f"migraciones: en ese orden, los objetos nuevos se quedan sin "
                f"permisos y el rol de la aplicación no los puede usar.")


def test_el_guion_sin_docker_no_lleva_una_lista_escrita_a_mano():
    """Recorre la carpeta con un glob, en lugar de nombrar los archivos.

    Es la corrección de fondo: con un glob, agregar una migración no obliga
    a acordarse de este guión. Con una lista, sí — y nadie se acordó.
    """
    guion = open(os.path.join(RAIZ, "scripts", "arranque_base.sh"),
                 encoding="utf-8").read()
    assert "db/migraciones/*.sql" in guion, (
        "El guión debe recorrer la carpeta de migraciones, no nombrar "
        "archivos uno por uno.")
    nombradas = re.findall(r"db/migraciones/(\d{3}_[a-z0-9_]+\.sql)", guion)
    assert not nombradas, (
        f"El guión nombra migraciones una por una: {nombradas}. Eso es lo "
        f"que se desincroniza.")
    assert "db/semilla/*.sql" in guion, (
        "Las semillas también: la 03, la 04 y la 05 insertan sobre objetos "
        "que crean las migraciones.")


def test_el_orden_del_guion_sin_docker_es_el_mismo_que_el_del_contenedor():
    guion = open(os.path.join(RAIZ, "scripts", "arranque_base.sh"),
                 encoding="utf-8").read()
    pos_esquema = guion.index("01_esquema.sql")
    pos_migraciones = guion.index("db/migraciones/*.sql")
    pos_permisos = guion.index("09_permisos.sh")
    pos_semillas = guion.index("db/semilla/*.sql")
    assert pos_esquema < pos_migraciones < pos_permisos < pos_semillas, (
        "El orden tiene que ser esquema, migraciones, permisos, semillas. "
        "Cualquier otro deja objetos sin privilegios o semillas que insertan "
        "sobre tablas que todavía no existen.")


def test_toda_accion_de_bitacora_del_codigo_existe_en_alguna_migracion():
    """La llave foránea que falla en silencio.

    Si el código registra una acción cuyo código no está en
    auditoria.tipo_accion, la inserción falla por llave foránea. Como el
    registro en bitácora va envuelto en un try para que no tumbe la
    operación principal, falla sin que nadie se entere: el sistema parece
    funcionar y no está registrando nada.
    """
    sql = "\n".join(
        open(os.path.join(MIGRACIONES, m), encoding="utf-8").read()
        for m in archivos_de(MIGRACIONES))
    sql += open(os.path.join(RAIZ, "db", "esquema", "01_esquema.sql"),
                encoding="utf-8").read()

    usadas = set()
    for carpeta, _, archivos in os.walk(os.path.join(RAIZ, "apps")):
        if "node_modules" in carpeta or "__pycache__" in carpeta:
            continue
        for archivo in archivos:
            if not archivo.endswith((".py", ".js")):
                continue
            texto = open(os.path.join(carpeta, archivo), encoding="utf-8",
                         errors="replace").read()
            usadas |= set(re.findall(r'_?bitacora\(\s*["\']([A-Z_]{4,})["\']', texto))
            usadas |= set(re.findall(r'registrar\(\s*["\']([A-Z_]{4,})["\']', texto))

    assert usadas, "No se encontró ninguna acción de bitácora en el código"

    # Se comprueba contra los INSERT a `auditoria.tipo_accion`, NO contra el
    # texto completo del SQL.
    #
    # La primera versión buscaba `a not in sql`, es decir si el código
    # aparecía en cualquier parte de cualquier migración. Eso la volvía
    # inútil justo en el caso que importa, y dejó pasar uno:
    # `INTERVENCION_SEGUIMIENTO` existe como PERMISO en
    # `usuarios.permiso`, así que la cadena aparecía en una migración y la
    # prueba daba por bueno un código que `auditoria.tipo_accion` no tenía.
    # El resultado era el silencio de siempre: ni un cambio de estado ni un
    # avance de intervención quedaban registrados.
    #
    # Un código que sirve de permiso y de acción a la vez es además
    # ambiguo al leer la bitácora, así que esto empuja a separarlos.
    declaradas = set()
    for bloque in re.findall(
            r"INSERT\s+INTO\s+auditoria\.tipo_accion\b(.*?);", sql,
            re.S | re.I):
        declaradas |= set(re.findall(r"\(\s*'([A-Z_]{4,})'", bloque))

    assert declaradas, (
        "No se encontró ningún INSERT a auditoria.tipo_accion. Si cambió la "
        "forma de declarar las acciones, esta prueba dejó de comprobar algo "
        "y hay que arreglarla, no borrarla.")

    faltan = sorted(a for a in usadas if a not in declaradas)
    assert not faltan, (
        f"Estas acciones se registran en el código y NO están declaradas en "
        f"auditoria.tipo_accion: {faltan}. La inserción en bitácora falla "
        f"por llave foránea, y como va envuelta en un try, falla en "
        f"silencio: el sistema parece funcionar y no registra nada.\n"
        f"Declaradas hoy: {sorted(declaradas)}")


def test_todo_resultado_de_bitacora_del_codigo_existe_en_alguna_migracion():
    """La MISMA llave foránea, por la otra columna. Y por la que falló.

    `auditoria.bitacora` tiene dos llaves foráneas: una contra
    `tipo_accion` y otra contra `resultado`. La prueba de arriba cubría la
    primera; esta existe porque la segunda sí estaba rota y nadie lo vio.

    El código escribía RECHAZADO_PERMISO y el catálogo no lo tenía. La
    inserción fallaba por llave foránea y, como el registro va envuelto en
    un try para que un problema de auditoría no tumbe la operación
    principal, fallaba en silencio.

    Lo que se perdía es lo que un auditor busca primero: TODOS los accesos
    denegados por falta de permiso. El 403 llegaba al usuario y no quedaba
    rastro de que hubiera ocurrido. Una bitácora a la que le faltan
    precisamente los intentos rechazados es peor que no tener bitácora,
    porque parece completa.
    """
    sql = "\n".join(
        open(os.path.join(MIGRACIONES, m), encoding="utf-8").read()
        for m in archivos_de(MIGRACIONES))
    sql += open(os.path.join(RAIZ, "db", "esquema", "01_esquema.sql"),
                encoding="utf-8").read()

    usados = set()
    for carpeta, _, archivos in os.walk(os.path.join(RAIZ, "apps")):
        if "node_modules" in carpeta or "__pycache__" in carpeta:
            continue
        for archivo in archivos:
            if not archivo.endswith((".py", ".js")):
                continue
            texto = open(os.path.join(carpeta, archivo), encoding="utf-8",
                         errors="replace").read()
            # registrar("ACCION", "RESULTADO") y _bitacora("ACCION", "RESULTADO")
            usados |= set(re.findall(
                r'(?:_?bitacora|registrar)\(\s*["\']?[A-Z_]*["\']?\s*,\s*'
                r'["\']([A-Z_]{4,})["\']', texto))
            # el caso condicional: "EXITO" if x else "PARCIAL"
            usados |= set(re.findall(
                r'["\']([A-Z_]{4,})["\']\s+if\s+\w+\s+else\s+["\']([A-Z_]{4,})["\']',
                texto) and [g for par in re.findall(
                r'["\']([A-Z_]{4,})["\']\s+if\s+\w+\s+else\s+["\']([A-Z_]{4,})["\']',
                texto) for g in par])

    # Se quedan solo los que parecen resultado y no acción: los resultados
    # son pocos y conocidos, y lo que importa es que ninguno falte.
    conocidos = {"EXITO", "RECHAZADO", "RECHAZADO_PERMISO", "ERROR_TECNICO",
                 "PARCIAL", "GRUPO_INSUFICIENTE", "PRESUPUESTO_AGOTADO",
                 "DENEGADO"}
    usados &= conocidos
    assert usados, "No se encontró ningún resultado de bitácora en el código"

    faltan = sorted(r for r in usados if f"'{r}'" not in sql)
    assert not faltan, (
        f"Estos resultados se escriben en la bitácora y no existen en "
        f"auditoria.resultado: {faltan}. La inserción falla por llave "
        f"foránea, y en silencio: se pierden justo los registros que "
        f"describen lo que el sistema negó.")


def test_no_hay_dos_etiquetas_para_el_mismo_hecho():
    """DENEGADO y RECHAZADO_PERMISO significaban lo mismo.

    Dos etiquetas para el mismo hecho vuelven la bitácora imposible de
    consultar: quien filtre por una se pierde la mitad de los casos y no
    tiene cómo saberlo.
    """
    usados = set()
    for carpeta, _, archivos in os.walk(os.path.join(RAIZ, "apps")):
        if "node_modules" in carpeta or "__pycache__" in carpeta:
            continue
        for archivo in archivos:
            if archivo.endswith((".py", ".js")):
                texto = open(os.path.join(carpeta, archivo), encoding="utf-8",
                             errors="replace").read()
                if '"DENEGADO"' in texto or "'DENEGADO'" in texto:
                    usados.add(os.path.join(carpeta, archivo))
    assert not usados, (
        f"Estos archivos usan DENEGADO, que significa lo mismo que "
        f"RECHAZADO_PERMISO: {sorted(usados)}")


# =========================================================================
# Las ocho garantías del modelo
# =========================================================================
# `gobernanza.fn_verificar_garantias()` es lo que se corre en la
# demostración para mostrar que las garantías de privacidad se sostienen a
# nivel de MODELO y no solo de interfaz. Que se cumplan es lo que estas
# pruebas comprueban; que exista una garantía por cada vía de entrada es
# lo que comprueba la segunda, y es lo que se olvida: las migraciones 011
# y 012 abrieron dos vías nuevas, y durante un rato ninguna garantía las
# miraba.

def test_las_ocho_garantias_del_modelo_se_cumplen():
    from comun.datos import consultar
    filas = consultar("SELECT garantia, cumple, detalle "
                      "  FROM gobernanza.fn_verificar_garantias() "
                      " ORDER BY garantia")
    assert len(filas) == 8, (
        f"Se esperaban ocho garantias y hay {len(filas)}. Si se agrego una "
        f"via de entrada, le toca su garantia; si se quito una garantia, "
        f"hay que poder explicar por que.")
    incumplidas = [(f["garantia"], f["detalle"]) for f in filas
                   if not f["cumple"]]
    assert not incumplidas, f"Garantias que NO se cumplen: {incumplidas}"


def test_cada_esquema_que_recibe_datos_de_fuera_tiene_su_garantia():
    """Las vías de entrada son las que hay que vigilar.

    `integracion` recibe del sistema corporativo, que tiene los nombres,
    los puestos y los sueldos de toda la organización. `sincronizacion`
    recibe de las aplicaciones cliente. Un esquema de entrada sin garantía
    es una puerta sin revisar.
    """
    from comun.datos import consultar
    nombres = " ".join(f["garantia"] for f in consultar(
        "SELECT garantia FROM gobernanza.fn_verificar_garantias()")).lower()
    for esquema, palabra in (("integracion", "integracion"),
                             ("sincronizacion", "sincronizacion"),
                             ("autoreporte", "autoreporte"),
                             ("intervencion", "intervencion")):
        assert palabra in nombres, (
            f"El esquema '{esquema}' recibe o guarda datos y ninguna "
            f"garantia lo menciona.")


def test_la_garantia_de_integracion_no_depende_del_filtro_del_servicio():
    """Comprueba contra el catálogo del sistema, no contra el código.

    El filtro de `integration-service` protege de lo que ENTRA por su API.
    La garantía comprueba que no haya DÓNDE guardarlo, y es la que sigue
    valiendo el día que alguien agregue una columna «para depurar»: el
    filtro seguiría funcionando igual, y la columna ya estaría ahí.
    """
    from comun.datos import consultar
    fuente = consultar(
        "SELECT prosrc FROM pg_proc p JOIN pg_namespace n "
        "    ON n.oid = p.pronamespace "
        " WHERE n.nspname = 'gobernanza' "
        "   AND p.proname = 'fn_verificar_garantias'")[0]["prosrc"]
    assert "information_schema.columns" in fuente
    assert "table_schema='integracion'" in fuente.replace(" ", "")
