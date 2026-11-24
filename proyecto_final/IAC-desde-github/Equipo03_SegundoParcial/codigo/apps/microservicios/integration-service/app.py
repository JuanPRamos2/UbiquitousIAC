"""
integration-service — la puerta estrecha hacia el sistema corporativo.

POR QUÉ ESTE SERVICIO ES EL MÁS PELIGROSO DEL PROYECTO
-------------------------------------------------------
Conectar un sistema corporativo de recursos humanos a una plataforma de
bienestar es el momento donde este proyecto se puede romper, y no por un
error técnico. El sistema de origen **tiene** los nombres, los puestos,
los sueldos y las fechas de nacimiento. La vía de integración es por donde
entrarían.

Y casi siempre entran sin que nadie lo decida: el sistema de origen manda
su registro completo, el de destino guarda «lo que venga, por si acaso», y
seis meses después hay una tabla con datos que nadie pidió y que ninguna
funcionalidad usa.

Así que esto no es un espejo del padrón corporativo. Es una puerta
estrecha, con registro de lo que pasó y de lo que se rechazó.

LAS CINCO DECISIONES
--------------------
1. **No crea personas. Nunca.** Es la menos obvia y la más importante. Una
   persona creada por una importación no tendría registro de
   consentimiento, y el consentimiento es lo que habilita que su respuesta
   cuente (RN-02). Una persona creada por aquí podría empezar a aparecer
   en agregados sin haber aceptado nada. Un identificador externo sin
   seudónimo correspondiente es un hallazgo, no un alta.

2. **Los campos de persona se rechazan, no se ignoran.** Ignorarlos sería
   lo cómodo y tiene una consecuencia mala: el sistema de origen sigue
   mandándolos, nadie se entera, y el día que alguien «mejore» el
   importador para no desperdiciar datos, ya están llegando. Un rechazo
   ruidoso obliga a arreglar el origen.

3. **Validar y aplicar son dos modos, y validar no escribe nada.** Quien
   integra necesita poder preguntar «¿esto pasaría?» sin arriesgarse.

4. **Aplicar es todo o nada.** Decisión OPUESTA a la de `sync-service`, y
   a propósito: un lote de autoreportes a medio aplicar son respuestas
   guardadas, que es un resultado útil. Un árbol organizacional a medio
   aplicar son unidades huérfanas, y el alcance de todos los perfiles se
   calcula recorriendo ese árbol. Un árbol roto significa gente viendo
   datos de áreas que no le tocan, o no viendo los suyos.

5. **La jerarquía importada tiene que cuadrar.** La plantilla de un padre
   debe ser la suma de sus hijas, y la validación vive en la base
   (`integracion.fn_validar_arbol_propuesto`). No es pulcritud: el control
   de inferencia resta la plantilla del padre menos la de las hijas
   conocidas para detectar si alguien está aislando un grupo por debajo
   del umbral k. Con un árbol que no cuadra, ese resto da cualquier cosa.
   **Esto ya pasó en este proyecto**: la semilla creaba padres con
   plantilla propia y el control quedó neutralizado hasta la migración
   008. Una importación sin esta validación lo rompería otra vez, y esta
   vez desde fuera.
"""
import hashlib
import json
import os
import re

from flask import g, request

from comun import (ErrorApi, VERSION_API, crear_servicio, cuerpo_peticion,
                   limite_consumo, obtener_redis, responder, requiere_permiso,
                   requiere_token)
from comun.datos import consultar, consultar_uno, cursor, ping as ping_pg

os.environ.setdefault("NOMBRE_SERVICIO", "integration-service")

MODOS = {"VALIDAR", "APLICAR"}
TIPOS = {"ESTRUCTURA", "IDENTIFICADORES"}

# Los campos que NO pueden venir en una integración. La lista es explícita
# y no una heurística: una heurística deja pasar lo que no previó, y aquí
# lo que se cuela se queda.
#
# Se comparan en minúsculas y sin acentos, y basta que el nombre del campo
# CONTENGA uno de estos para rechazarlo: un sistema corporativo manda
# `nombre_completo`, `primer_apellido`, `correo_institucional`, y una
# comparación exacta los dejaría pasar todos.
CAMPOS_DE_PERSONA = (
    "nombre", "apellido", "correo", "email", "telefono", "celular",
    "curp", "rfc", "nss", "imss", "direccion", "domicilio",
    "fecha_nacimiento", "nacimiento", "edad", "sexo", "genero",
    "estado_civil", "salario", "sueldo", "puesto", "nomina",
    "empleado_id", "numero_empleado", "foto", "huella",
)

# Campos que SÍ se admiten en un renglón de estructura. Lista blanca y no
# lista negra para la estructura: aquí se sabe exactamente qué se necesita,
# y cualquier cosa de más es algo que el origen manda y nadie pidió.
CAMPOS_ESTRUCTURA = {"unidad_organizacional_id", "nombre_unidad",
                     "unidad_padre_id", "tipo", "plantilla_declarada",
                     "activa", "descripcion", "nivel_jerarquico"}

CAMPOS_IDENTIFICADORES = {"identificador_externo", "seudonimo_id", "activo"}

PATRON_UNIDAD = re.compile(r"^[A-Za-z0-9_\-\.]{2,40}$")

# Los tipos de unidad válidos NO se escriben aquí a mano: se leen de la
# restricción de la base.
#
# El primer intento los tenía como un literal en el código, y la lista
# había quedado distinta de la de la base: incluía GERENCIA y SITIO, que
# la base rechaza, y le faltaba DEPARTAMENTO, que la base acepta. El
# efecto era de los peores: el servicio validaba el archivo, lo declaraba
# correcto, y después reventaba al insertar. Y como aplicar es todo o
# nada, el archivo entero fallaba con un mensaje que no decía qué campo
# era el problema.
#
# Una lista escrita a mano al lado de una restricción de la base se separa
# de ella en algún momento, y la separación solo se ve al escribir.
_TIPOS_CACHE = None


def tipos_unidad():
    """Los tipos que la base acepta, leídos de su propia restricción."""
    global _TIPOS_CACHE
    if _TIPOS_CACHE is None:
        fila = consultar_uno(
            "SELECT pg_get_constraintdef(oid) AS d FROM pg_constraint "
            " WHERE conname = 'unidad_organizacional_tipo_check'")
        if fila:
            _TIPOS_CACHE = set(re.findall(r"'([A-Z_]+)'::", fila["d"]))
        if not _TIPOS_CACHE:
            # Sin restricción declarada no se inventa una lista: se deja
            # pasar y que la base decida. Inventarla aquí reintroduciría
            # justo la divergencia que esto viene a evitar.
            _TIPOS_CACHE = set()
    return _TIPOS_CACHE


def _ping_redis():
    obtener_redis().ping()


app = crear_servicio(
    "integration-service",
    "Integracion controlada con el sistema corporativo: estructura "
    "organizacional e identificadores seudonimizados",
    comprobaciones={"postgresql": ping_pg, "redis": _ping_redis})

from contrato import montar as _montar_contrato  # noqa: E402
_montar_contrato(app)

BASE = f"/api/{VERSION_API}/integracion"


def _bitacora(accion, resultado, recurso=None):
    try:
        with cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO auditoria.bitacora (actor_usuario_id, "
                " actor_perfil, accion, tipo_recurso, recurso_id, resultado, "
                " correlacion_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                ((g.get("actor") or {}).get("sub"),
                 ((g.get("actor") or {}).get("perfil") or "ANONIMO")[:30],
                 accion, "INTEGRACION", str(recurso) if recurso else None,
                 resultado, getattr(g, "correlacion_id", "")))
    except Exception:
        app.logger.error("No se pudo escribir en la bitacora: %s", accion)


# =========================================================================
# Validación contra el XSD
# =========================================================================
# POR QUÉ SE VALIDA CONTRA ESQUEMA Y NO SOLO CON LA LISTA DE CAMPOS
# ------------------------------------------------------------------
# El servicio ya rechaza los campos de persona con una lista explícita.
# Pero una lista es una enumeración, y una enumeración siempre deja fuera
# lo que no previó: un `nss_trabajador` que a nadie se le ocurrió poner
# en ella pasaría.
#
# El esquema invierte la carga. Declara lo PERMITIDO —los tipos de renglón
# son `xs:all` cerrado, sin `xs:any`— y todo lo demás se rechaza sin tener
# que haberlo anticipado.
#
# Las dos defensas conviven a propósito y ninguna sobra: el esquema solo
# actúa sobre XML, mientras que la lista cubre también el JSON y además
# nombra el campo culpable, que es lo que permite arreglar el origen. Un
# «este elemento no se esperaba» no le dice al equipo del sistema
# corporativo qué tiene que quitar de su extracción.
#
# Y la validación va ANTES de leer el contenido: un archivo mal formado se
# rechaza sin que una sola línea llegue al código que interpreta renglones.
CARPETA_XSD = os.environ.get(
    "CONTRATOS_XSD",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))), "contratos", "xml"))

_esquema = None


def esquema_xsd():
    """El XSD compilado, una sola vez.

    Si no se puede cargar NO se finge que sí: el servicio sigue
    atendiendo —la lista de campos y las validaciones de la base siguen
    puestas— pero lo dice en la respuesta. Un servicio que anuncia
    «validado contra XSD» sin haber validado nada es peor que uno que
    declara no poder hacerlo.
    """
    global _esquema
    if _esquema is None:
        try:
            from lxml import etree
            ruta = os.path.join(CARPETA_XSD, "integracion.xsd")
            _esquema = etree.XMLSchema(etree.parse(ruta))
        except Exception as error:                       # noqa: BLE001
            app.logger.error("No se pudo cargar integracion.xsd: %s", error)
            _esquema = False
    return _esquema


def validar_contra_xsd(crudo, raiz_esperada):
    """Valida el cuerpo XML. Lanza ErrorApi con el detalle del validador.

    El detalle se devuelve tal cual lo da el validador —con la línea y el
    elemento— porque quien tiene que arreglar el archivo no es quien opera
    esta plataforma, y un «XML invalido» a secas obliga a una cadena de
    correos.
    """
    esquema = esquema_xsd()
    if esquema is False:
        return "NO_DISPONIBLE"

    from lxml import etree
    try:
        documento = etree.fromstring(crudo.encode("utf-8"))
    except etree.XMLSyntaxError as error:
        raise ErrorApi("XML_MAL_FORMADO", str(error), 400)

    etiqueta = etree.QName(documento).localname
    if etiqueta != raiz_esperada:
        raise ErrorApi(
            "RAIZ_INESPERADA",
            f"El elemento raiz es '{etiqueta}' y este endpoint espera "
            f"'{raiz_esperada}'. Revisa que no estes mandando el archivo de "
            f"estructura al endpoint de identificadores o al reves.", 422)

    if not esquema.validate(documento):
        detalles = [{"campo": f"linea {e.line}", "problema": e.message}
                    for e in esquema.error_log][:10]
        raise ErrorApi(
            "XSD_INVALIDO",
            "El archivo no cumple integracion.xsd. El esquema declara lo "
            "PERMITIDO, asi que un elemento no esperado —un campo de "
            "persona, por ejemplo— lo hace fallar aunque no este en ninguna "
            "lista negra. El esquema se publica en "
            "/api/v1/integracion/esquema.xsd para poder validar antes de "
            "mandar.", 422, detalles)
    return "VALIDADO"


def _normalizar(nombre):
    """Minúsculas y sin acentos, para comparar nombres de campo.

    Sin esto, `Teléfono` y `telefono` serían campos distintos y el primero
    pasaría. Un filtro que se saltea cambiando una tilde no es un filtro.
    """
    import unicodedata
    plano = unicodedata.normalize("NFKD", str(nombre))
    plano = "".join(c for c in plano if not unicodedata.combining(c))
    return plano.lower().strip()


def _campos_de_persona_en(renglon, permitidos):
    """Qué campos de persona trae este renglón.

    LA LISTA BLANCA GANA SOBRE LA NEGRA, Y HACE FALTA QUE SEA ASÍ
    -------------------------------------------------------------
    La coincidencia con la lista negra es por CONTENIDO del nombre, porque
    un sistema corporativo manda `nombre_completo`, `primer_apellido` y
    `correo_institucional`, y una comparación exacta contra «nombre»,
    «apellido» y «correo» los dejaría pasar todos.

    Pero por contenido, «nombre» también coincide con `nombre_unidad`, que
    es un campo legítimo y obligatorio de la estructura. El primer intento
    de este servicio rechazaba por eso TODO archivo de estructura bien
    formado. Lo destaparon las pruebas: veinte fallaron de golpe.

    Así que los campos de la lista blanca —los que este servicio
    enumeró como necesarios— no se revisan contra la negra. No es una
    excepción incómoda: es el orden correcto. La lista blanca dice qué se
    usa, y la negra solo tiene que juzgar lo que llegó de más.

    Devuelve los nombres tal como llegaron, no los normalizados: quien
    tiene que arreglar el archivo necesita ver el nombre que escribió.
    """
    encontrados = []
    for campo in renglon:
        if campo in permitidos:
            continue
        plano = _normalizar(campo)
        for prohibido in CAMPOS_DE_PERSONA:
            if prohibido in plano:
                encontrados.append(campo)
                break
    return encontrados


def _como_lista(valor, nombre_campo):
    """Normaliza la lista venga de JSON o de XML.

    El serializador XML del proyecto envuelve en plural y nombra en
    singular, y con un solo elemento devuelve el diccionario en vez de una
    lista de uno.
    """
    if valor is None:
        return []
    if isinstance(valor, list):
        return valor
    if isinstance(valor, dict):
        if len(valor) == 1:
            interno = next(iter(valor.values()))
            if isinstance(interno, list):
                return interno
            if isinstance(interno, dict):
                return [interno]
        return [valor]
    raise ErrorApi("VALIDACION",
                   f"'{nombre_campo}' tiene que ser una lista.", 422)


def _sello(contenido):
    texto = json.dumps(contenido, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _fuente_autorizada(fuente_id, tipo):
    """Una fuente no registrada no integra, y una registrada solo lo suyo.

    Lo normal es aceptar de cualquiera que traiga un token válido, y
    entonces cualquier componente con credenciales de la organización
    puede reescribir el árbol organizacional.
    """
    fuente = consultar_uno(
        "SELECT fuente_id, nombre, activa, admite_estructura, "
        "       admite_identificadores, motivo FROM integracion.fuente "
        " WHERE fuente_id = %s", (fuente_id,))
    if not fuente:
        raise ErrorApi("FUENTE_NO_REGISTRADA",
                       f"La fuente '{fuente_id}' no esta registrada. Una "
                       f"fuente no registrada no puede integrar: si "
                       f"cualquiera con un token valido pudiera, cualquier "
                       f"componente de la organizacion podria reescribir el "
                       f"arbol organizacional.", 403)
    if not fuente["activa"]:
        raise ErrorApi("FUENTE_INACTIVA",
                       f"La fuente '{fuente_id}' esta registrada pero no "
                       f"activa. Motivo asentado: {fuente['motivo']}", 403)
    columna = ("admite_estructura" if tipo == "ESTRUCTURA"
               else "admite_identificadores")
    if not fuente[columna]:
        raise ErrorApi("FUENTE_SIN_ESA_FINALIDAD",
                       f"La fuente '{fuente_id}' no esta autorizada a "
                       f"entregar {tipo.lower()}. Que sea explicito por "
                       f"fuente evita que una integracion creada para una "
                       f"cosa se use despues para otra sin que nadie lo "
                       f"revise. Motivo asentado: {fuente['motivo']}", 403)
    return fuente


def _abrir_ingesta(fuente_id, tipo, modo, formato, renglones, sello):
    with cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO integracion.ingesta (fuente_id, tipo, modo, formato, "
            " actor_usuario_id, renglones, veredicto, sello_sha256, "
            " correlacion_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "RETURNING ingesta_id",
            (fuente_id, tipo, modo, formato, (g.get("actor") or {}).get("sub"),
             renglones, "RECHAZADA", sello, getattr(g, "correlacion_id", "")))
        return cur.fetchone()["ingesta_id"]


def _guardar_hallazgos(ingesta_id, hallazgos):
    if not hallazgos:
        return
    with cursor(commit=True) as cur:
        for h in hallazgos:
            cur.execute(
                "INSERT INTO integracion.hallazgo (ingesta_id, renglon, "
                " campo, codigo, severidad, detalle) VALUES (%s,%s,%s,%s,%s,%s)",
                (ingesta_id, h.get("renglon"), h.get("campo"),
                 h["codigo"], h.get("severidad", "ERROR"), h["detalle"]))


def _cerrar_ingesta(ingesta_id, veredicto, aplicados, errores, advertencias):
    with cursor(commit=True) as cur:
        cur.execute(
            "UPDATE integracion.ingesta SET veredicto=%s, aplicados=%s, "
            " errores=%s, advertencias=%s WHERE ingesta_id=%s",
            (veredicto, aplicados, errores, advertencias, ingesta_id))


def _leer_peticion(tipo, raiz_xml):
    """Lo común a los dos endpoints: fuente, modo, formato y renglones.

    El orden importa: si el cuerpo viene en XML se valida contra el XSD
    ANTES de interpretarlo. Validar después sería validar algo que ya se
    leyó, y para entonces el código que interpreta renglones ya habría
    visto el archivo.
    """
    validacion = "NO_APLICA"
    enviado_previo = (request.content_type or "").split(";")[0].strip().lower()
    if enviado_previo in ("application/xml", "text/xml"):
        crudo = request.get_data(as_text=True)
        if not crudo.strip():
            raise ErrorApi("CUERPO_VACIO", "No llego ningun contenido.", 400)
        validacion = validar_contra_xsd(crudo, raiz_xml)

    cuerpo = cuerpo_peticion()
    fuente_id = str(cuerpo.get("fuente_id") or "").strip()
    modo = str(cuerpo.get("modo") or "VALIDAR").strip().upper()

    problemas = []
    if not fuente_id:
        problemas.append({"campo": "fuente_id", "problema": "obligatorio"})
    if modo not in MODOS:
        problemas.append({"campo": "modo",
                          "problema": f"uno de: {', '.join(sorted(MODOS))}. "
                                      f"VALIDAR no escribe nada."})
    if problemas:
        raise ErrorApi("VALIDACION", "La peticion tiene campos invalidos.",
                       422, problemas)

    formato = "XML" if enviado_previo in ("application/xml",
                                          "text/xml") else "JSON"
    _fuente_autorizada(fuente_id, tipo)
    return cuerpo, fuente_id, modo, formato, validacion


# =========================================================================
# Estructura organizacional
# =========================================================================
@app.post(f"{BASE}/estructura")
@requiere_permiso("IMPORTACION_APLICAR", "UNIDAD_ADMIN")
def estructura():
    """Importa el árbol organizacional. Todo o nada.

    En modo VALIDAR no escribe una sola fila del árbol: solo la ingesta y
    sus hallazgos, que son el registro de que alguien preguntó.
    """
    limite_consumo(maximo=20)
    cuerpo, fuente_id, modo, formato, validacion = _leer_peticion(
        "ESTRUCTURA", "ingesta_estructura")
    unidades = _como_lista(cuerpo.get("unidades"), "unidades")
    if not unidades:
        raise ErrorApi("VALIDACION", "No vienen unidades.", 422,
                       [{"campo": "unidades", "problema": "lista vacia"}])

    sello = _sello(unidades)
    ingesta_id = _abrir_ingesta(fuente_id, "ESTRUCTURA", modo, formato,
                                len(unidades), sello)
    hallazgos = []
    limpias = []

    # ---- Paso 1: renglón por renglón, lo que se puede ver sin la base ----
    for indice, renglon in enumerate(unidades, start=1):
        if not isinstance(renglon, dict):
            hallazgos.append({"renglon": indice, "codigo": "RENGLON_INVALIDO",
                              "detalle": "No es un objeto."})
            continue

        # Los campos de persona se rechazan, no se ignoran (decisión 2).
        intrusos = _campos_de_persona_en(renglon, CAMPOS_ESTRUCTURA)
        if intrusos:
            hallazgos.append({
                "renglon": indice, "campo": ", ".join(intrusos),
                "codigo": "CAMPO_DE_PERSONA",
                "detalle": f"El renglon trae campos de persona: "
                           f"{', '.join(intrusos)}. Se rechaza en lugar de "
                           f"ignorarse: si se ignoraran, el sistema de "
                           f"origen seguiria mandandolos, nadie se "
                           f"enteraria, y el dia que alguien «mejore» el "
                           f"importador para no desperdiciar datos, ya "
                           f"estarian llegando. Arregla el origen."})
            continue

        sobrantes = set(renglon) - CAMPOS_ESTRUCTURA
        if sobrantes:
            hallazgos.append({
                "renglon": indice, "campo": ", ".join(sorted(sobrantes)),
                "codigo": "CAMPO_NO_ESPERADO", "severidad": "ADVERTENCIA",
                "detalle": f"Campos que esta integracion no usa: "
                           f"{', '.join(sorted(sobrantes))}. No se guardan. "
                           f"Si el origen los manda por costumbre, conviene "
                           f"quitarlos: un campo que se manda y no se usa "
                           f"acaba guardandose algun dia."})

        uid = str(renglon.get("unidad_organizacional_id") or "").strip()
        nombre = str(renglon.get("nombre_unidad") or "").strip()
        padre = renglon.get("unidad_padre_id")
        padre = str(padre).strip() if padre not in (None, "") else None
        tipo_u = str(renglon.get("tipo") or "AREA").strip().upper()

        if not PATRON_UNIDAD.match(uid):
            hallazgos.append({
                "renglon": indice, "campo": "unidad_organizacional_id",
                "codigo": "IDENTIFICADOR_INVALIDO",
                "detalle": f"'{uid}' no sirve como identificador de unidad. "
                           f"Se admiten letras, numeros, guion, guion bajo y "
                           f"punto, entre 2 y 40 caracteres."})
            continue
        if not nombre:
            hallazgos.append({"renglon": indice, "campo": "nombre_unidad",
                              "codigo": "CAMPO_OBLIGATORIO",
                              "detalle": "La unidad necesita nombre."})
            continue
        validos = tipos_unidad()
        if validos and tipo_u not in validos:
            hallazgos.append({
                "renglon": indice, "campo": "tipo",
                "codigo": "TIPO_INVALIDO",
                "detalle": f"'{tipo_u}' no es un tipo de unidad. Validos: "
                           f"{', '.join(sorted(validos))}."})
            continue
        try:
            plantilla = int(renglon.get("plantilla_declarada", 0))
        except (TypeError, ValueError):
            hallazgos.append({
                "renglon": indice, "campo": "plantilla_declarada",
                "codigo": "NO_ES_ENTERO",
                "detalle": f"'{renglon.get('plantilla_declarada')}' no es un "
                           f"entero. Sin plantilla no se puede validar que "
                           f"la jerarquia cuadre, y de eso depende el "
                           f"control de inferencia."})
            continue
        if plantilla < 0:
            hallazgos.append({"renglon": indice, "campo": "plantilla_declarada",
                              "codigo": "PLANTILLA_NEGATIVA",
                              "detalle": "No puede ser negativa."})
            continue

        limpias.append({"unidad_organizacional_id": uid,
                        "nombre": nombre,
                        "unidad_padre_id": padre,
                        "tipo": tipo_u,
                        "plantilla_declarada": plantilla,
                        "activa": bool(renglon.get("activa", True)),
                        "descripcion": renglon.get("descripcion")})

    # Identificadores repetidos dentro del mismo archivo. Sin esto, el
    # último gana en silencio y el archivo parece haberse aplicado entero.
    vistos = {}
    for i, u in enumerate(limpias, start=1):
        uid = u["unidad_organizacional_id"]
        if uid in vistos:
            hallazgos.append({
                "renglon": i, "campo": "unidad_organizacional_id",
                "codigo": "IDENTIFICADOR_REPETIDO",
                "detalle": f"'{uid}' viene mas de una vez en el archivo. "
                           f"Aplicarlo haria que el ultimo gane en silencio "
                           f"y el archivo pareceria haberse aplicado entero."})
        vistos[uid] = i

    # ---- Paso 2: el árbol como conjunto, validado en la base ----
    if limpias:
        for fila in consultar(
                "SELECT codigo, campo, detalle FROM "
                " integracion.fn_validar_arbol_propuesto(%s::jsonb)",
                (json.dumps([{"unidad_organizacional_id": u["unidad_organizacional_id"],
                              "unidad_padre_id": u["unidad_padre_id"],
                              "plantilla_declarada": u["plantilla_declarada"]}
                             for u in limpias]),)):
            hallazgos.append({"codigo": fila["codigo"], "campo": fila["campo"],
                              "detalle": fila["detalle"]})

    _guardar_hallazgos(ingesta_id, hallazgos)
    errores = [h for h in hallazgos if h.get("severidad", "ERROR") == "ERROR"]
    advertencias = [h for h in hallazgos
                    if h.get("severidad") == "ADVERTENCIA"]

    # ---- Paso 3: aplicar, si procede ----
    if errores:
        _cerrar_ingesta(ingesta_id, "RECHAZADA", 0, len(errores),
                        len(advertencias))
        _bitacora("INTEGRACION_RECHAZADA", "RECHAZADO", ingesta_id)
        # Un segundo registro, con su propia acción, cuando el motivo fue
        # que venían campos de persona. Se separa porque no es un rechazo
        # cualquiera: describe un sistema de origen que está mandando datos
        # que no debería, y eso hay que poder contarlo por separado.
        if any(h["codigo"] == "CAMPO_DE_PERSONA" for h in errores):
            _bitacora("CAMPO_DE_PERSONA_RECHAZADO", "RECHAZADO", ingesta_id)
        return responder(_informe(ingesta_id, "RECHAZADA", len(unidades), 0,
                                  hallazgos, validacion), 422, raiz="ingesta_respuesta")

    if modo == "VALIDAR":
        _cerrar_ingesta(ingesta_id, "SOLO_VALIDADA", 0, 0, len(advertencias))
        _bitacora("INTEGRACION_VALIDADA", "SOLO_VALIDADA", ingesta_id)
        informe = _informe(ingesta_id, "SOLO_VALIDADA", len(unidades), 0,
                           hallazgos, validacion)
        informe["nota"] = ("Pasaria. No se escribio NADA del arbol: el modo "
                           "era VALIDAR. 'SOLO_VALIDADA' se distingue de "
                           "'ACEPTADA' a proposito, porque confundirlas haria "
                           "creer que el arbol ya se actualizo.")
        return responder(informe, 200, raiz="ingesta_respuesta")

    # Todo o nada: una sola transacción para el árbol completo (decisión 4).
    # Las unidades se ordenan por nivel —primero las que no tienen padre—
    # porque la llave foránea del padre se comprueba al insertar.
    orden = _por_niveles(limpias)
    try:
        with cursor(commit=True) as cur:
            for u in orden:
                cur.execute(
                    "INSERT INTO organizacion.unidad_organizacional "
                    " (unidad_organizacional_id, nombre, tipo, "
                    "  unidad_padre_id, plantilla_declarada, activa, "
                    "  descripcion) VALUES (%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (unidad_organizacional_id) DO UPDATE SET "
                    "  nombre = EXCLUDED.nombre, tipo = EXCLUDED.tipo, "
                    "  unidad_padre_id = EXCLUDED.unidad_padre_id, "
                    "  plantilla_declarada = EXCLUDED.plantilla_declarada, "
                    "  activa = EXCLUDED.activa, "
                    "  descripcion = EXCLUDED.descripcion, "
                    "  fecha_actualizacion = now()",
                    (u["unidad_organizacional_id"], u["nombre"], u["tipo"],
                     u["unidad_padre_id"], u["plantilla_declarada"],
                     u["activa"], u["descripcion"]))
    except Exception as error:                           # noqa: BLE001
        app.logger.error("Fallo al aplicar la estructura: %s", error)
        _guardar_hallazgos(ingesta_id, [{
            "codigo": "APLICACION_FALLIDA",
            "detalle": "No se aplico nada: la transaccion se deshizo "
                       "completa. Un arbol a medio aplicar dejaria unidades "
                       "huerfanas, y el alcance de todos los perfiles se "
                       "calcula recorriendo ese arbol."}])
        _cerrar_ingesta(ingesta_id, "RECHAZADA", 0, len(errores) + 1,
                        len(advertencias))
        raise ErrorApi("APLICACION_FALLIDA",
                       "No se pudo aplicar la estructura. No se aplico nada: "
                       "es todo o nada a proposito.", 409)

    _cerrar_ingesta(ingesta_id, "ACEPTADA", len(limpias), 0,
                    len(advertencias))
    _bitacora("INTEGRACION_APLICADA", "EXITO", ingesta_id)

    # Se vuelve a comprobar contra la base, DESPUÉS de escribir. La
    # validación previa mira el archivo; esta mira el árbol que quedó, que
    # incluye unidades que ya estaban y que el archivo no tocó.
    inconsistentes = consultar("SELECT * FROM gobernanza.fn_jerarquia_consistente()")
    informe = _informe(ingesta_id, "ACEPTADA", len(unidades), len(limpias),
                       hallazgos, validacion)
    informe["jerarquia_tras_aplicar"] = {
        "consistente": not inconsistentes,
        "unidades_que_no_cuadran": [dict(f) for f in inconsistentes],
        "por_que_importa":
            "El control de inferencia resta la plantilla del padre menos la "
            "de las hijas conocidas. Si el arbol resultante no cuadra, ese "
            "resto da cualquier cosa y el control deja de servir. Se "
            "comprueba DESPUES de escribir porque el arbol final incluye "
            "unidades que ya estaban y que este archivo no toco.",
    }
    return responder(informe, 200, raiz="ingesta_respuesta")


def _por_niveles(unidades):
    """Ordena para que ningún padre se inserte después de su hija.

    La llave foránea del padre se comprueba al insertar, así que un
    archivo que liste la hija antes del padre fallaría aunque el árbol sea
    correcto. Ordenar es más amable que exigirle al origen un orden.
    """
    pendientes = {u["unidad_organizacional_id"]: u for u in unidades}
    ya = set()
    salida = []
    # Las que cuelgan de algo que ya existe en la base o de nada arrancan.
    existentes = {f["unidad_organizacional_id"] for f in consultar(
        "SELECT unidad_organizacional_id FROM organizacion.unidad_organizacional")}
    for _ in range(len(pendientes) + 1):
        avance = False
        for uid, u in list(pendientes.items()):
            padre = u["unidad_padre_id"]
            if padre in (None, "") or padre in ya or padre in existentes:
                salida.append(u)
                ya.add(uid)
                del pendientes[uid]
                avance = True
        if not pendientes or not avance:
            break
    # Si quedó algo sin colocar, el validador ya lo reportó como ciclo o
    # padre inexistente; se agrega al final para no perderlo en silencio.
    salida.extend(pendientes.values())
    return salida


def _informe(ingesta_id, veredicto, renglones, aplicados, hallazgos,
             validacion="NO_APLICA"):
    errores = [h for h in hallazgos if h.get("severidad", "ERROR") == "ERROR"]
    advertencias = [h for h in hallazgos if h.get("severidad") == "ADVERTENCIA"]
    return {
        "ingesta_id": ingesta_id,
        "veredicto": veredicto,
        # Se dice si el archivo paso por el esquema, y no se da por hecho.
        # NO_APLICA es un cuerpo JSON —el XSD solo valida XML—, y
        # NO_DISPONIBLE es que el esquema no se pudo cargar: anunciar
        # «validado contra XSD» sin haber validado seria peor que decir
        # que no se pudo.
        "validacion_xsd": validacion,
        "renglones": renglones,
        "aplicados": aplicados,
        "errores": len(errores),
        "advertencias": len(advertencias),
        "hallazgos": [
            {"renglon": h.get("renglon"), "campo": h.get("campo"),
             "codigo": h["codigo"],
             "severidad": h.get("severidad", "ERROR"),
             "detalle": h["detalle"]}
            for h in hallazgos],
    }


# =========================================================================
# Identificadores seudonimizados
# =========================================================================
@app.post(f"{BASE}/identificadores")
@requiere_permiso("IMPORTACION_APLICAR", "USUARIO_ADMIN")
def identificadores():
    """Sincroniza la correspondencia identificador externo ↔ seudónimo.

    **No crea personas** (decisión 1). Un identificador externo cuyo
    seudónimo no existe es un hallazgo, no un alta: una persona creada por
    aquí no tendría consentimiento y podría empezar a contar en agregados
    sin haber aceptado nada.
    """
    limite_consumo(maximo=20)
    cuerpo, fuente_id, modo, formato, validacion = _leer_peticion(
        "IDENTIFICADORES", "ingesta_identificadores")
    renglones = _como_lista(cuerpo.get("identificadores"), "identificadores")
    if not renglones:
        raise ErrorApi("VALIDACION", "No vienen identificadores.", 422,
                       [{"campo": "identificadores", "problema": "lista vacia"}])

    ingesta_id = _abrir_ingesta(fuente_id, "IDENTIFICADORES", modo, formato,
                                len(renglones), _sello(renglones))
    hallazgos, limpios = [], []

    for indice, renglon in enumerate(renglones, start=1):
        if not isinstance(renglon, dict):
            hallazgos.append({"renglon": indice, "codigo": "RENGLON_INVALIDO",
                              "detalle": "No es un objeto."})
            continue

        intrusos = _campos_de_persona_en(renglon, CAMPOS_IDENTIFICADORES)
        if intrusos:
            hallazgos.append({
                "renglon": indice, "campo": ", ".join(intrusos),
                "codigo": "CAMPO_DE_PERSONA",
                "detalle": f"Trae campos de persona: {', '.join(intrusos)}. "
                           f"Esta correspondencia guarda DOS CADENAS OPACAS "
                           f"y nada mas. Si guardara tambien el nombre o el "
                           f"numero de empleado, junto al seudonimo, "
                           f"reconstruiria la identificacion completa, que "
                           f"es justo lo que la seudonimizacion evita."})
            continue

        sobrantes = set(renglon) - CAMPOS_IDENTIFICADORES
        if sobrantes:
            hallazgos.append({
                "renglon": indice, "campo": ", ".join(sorted(sobrantes)),
                "codigo": "CAMPO_NO_ESPERADO", "severidad": "ADVERTENCIA",
                "detalle": f"Campos que no se usan: "
                           f"{', '.join(sorted(sobrantes))}. No se guardan."})

        externo = str(renglon.get("identificador_externo") or "").strip()
        seudonimo = str(renglon.get("seudonimo_id") or "").strip()
        if not externo or not seudonimo:
            hallazgos.append({
                "renglon": indice, "codigo": "CAMPO_OBLIGATORIO",
                "campo": "identificador_externo/seudonimo_id",
                "detalle": "Los dos son obligatorios."})
            continue

        # Aquí es donde se cumple la decisión 1.
        #
        # Se comprueba contra `consentimiento.v_estado_vigente` y no contra
        # `consentimiento.seudonimo`: el rol de la aplicación NO puede leer
        # esa tabla, porque es la que vincula el seudónimo con el empleado,
        # y ese vínculo no debe estar al alcance de ningún servicio. El
        # primer intento la consultaba y fallaba con «permission denied»,
        # que es la garantía funcionando.
        #
        # Y la vista es además la fuente correcta por el fondo del asunto:
        # lo que hace falta saber no es que el seudónimo exista, sino que
        # tenga un registro de consentimiento. Es exactamente la razón por
        # la que esta integración no crea personas.
        if not consultar_uno("SELECT 1 AS x FROM consentimiento.v_estado_vigente "
                             " WHERE seudonimo_id = %s LIMIT 1", (seudonimo,)):
            hallazgos.append({
                "renglon": indice, "campo": "seudonimo_id",
                "codigo": "SEUDONIMO_NO_EXISTE",
                "detalle": f"El seudonimo '{seudonimo}' no existe en esta "
                           f"plataforma, y la integracion NO crea personas. "
                           f"Una persona creada por aqui no tendria registro "
                           f"de consentimiento, y el consentimiento es lo "
                           f"que habilita que su respuesta cuente: podria "
                           f"empezar a aparecer en agregados sin haber "
                           f"aceptado nada. El alta de una persona pasa por "
                           f"el flujo de consentimiento, no por aqui."})
            continue

        limpios.append({"identificador_externo": externo,
                        "seudonimo_id": seudonimo,
                        "activo": bool(renglon.get("activo", True))})

    _guardar_hallazgos(ingesta_id, hallazgos)
    errores = [h for h in hallazgos if h.get("severidad", "ERROR") == "ERROR"]
    advertencias = [h for h in hallazgos if h.get("severidad") == "ADVERTENCIA"]

    if errores:
        _cerrar_ingesta(ingesta_id, "RECHAZADA", 0, len(errores),
                        len(advertencias))
        _bitacora("INTEGRACION_RECHAZADA", "RECHAZADO", ingesta_id)
        if any(h["codigo"] == "CAMPO_DE_PERSONA" for h in errores):
            _bitacora("CAMPO_DE_PERSONA_RECHAZADO", "RECHAZADO", ingesta_id)
        return responder(_informe(ingesta_id, "RECHAZADA", len(renglones), 0,
                                  hallazgos, validacion), 422, raiz="ingesta_respuesta")

    if modo == "VALIDAR":
        _cerrar_ingesta(ingesta_id, "SOLO_VALIDADA", 0, 0, len(advertencias))
        _bitacora("INTEGRACION_VALIDADA", "SOLO_VALIDADA", ingesta_id)
        informe = _informe(ingesta_id, "SOLO_VALIDADA", len(renglones), 0,
                           hallazgos, validacion)
        informe["nota"] = "Pasaria. No se escribio nada."
        return responder(informe, 200, raiz="ingesta_respuesta")

    try:
        with cursor(commit=True) as cur:
            for r in limpios:
                cur.execute(
                    "INSERT INTO integracion.identificador_externo "
                    " (fuente_id, identificador_externo, seudonimo_id, activo) "
                    "VALUES (%s,%s,%s,%s) "
                    "ON CONFLICT (fuente_id, identificador_externo) "
                    "DO UPDATE SET seudonimo_id = EXCLUDED.seudonimo_id, "
                    "              activo = EXCLUDED.activo",
                    (fuente_id, r["identificador_externo"], r["seudonimo_id"],
                     r["activo"]))
    except Exception as error:                           # noqa: BLE001
        app.logger.error("Fallo al aplicar identificadores: %s", error)
        _cerrar_ingesta(ingesta_id, "RECHAZADA", 0, 1, len(advertencias))
        # El caso típico: dos identificadores externos apuntando al mismo
        # seudónimo. La restricción lo impide porque la misma persona
        # entraría dos veces y contaría doble en cualquier conteo.
        raise ErrorApi("CORRESPONDENCIA_INVALIDA",
                       "No se aplico nada. Lo mas probable es que dos "
                       "identificadores externos apunten al mismo seudonimo: "
                       "la misma persona entraria dos veces y contaria doble "
                       "en cualquier conteo.", 409)

    _cerrar_ingesta(ingesta_id, "ACEPTADA", len(limpios), 0, len(advertencias))
    _bitacora("INTEGRACION_APLICADA", "EXITO", ingesta_id)
    return responder(_informe(ingesta_id, "ACEPTADA", len(renglones),
                              len(limpios), hallazgos, validacion),
                     200, raiz="ingesta_respuesta")


# =========================================================================
# Consulta
# =========================================================================
@app.get(f"{BASE}/fuentes")
@requiere_token
def fuentes():
    """Las fuentes registradas, con qué tiene permitido mandar cada una.

    Incluye las registradas y NO autorizadas, con su motivo. Están ahí a
    propósito: una fuente ausente de la lista parece un olvido, y una
    presente con el motivo escrito es una decisión que alguien tomó.
    """
    limite_consumo(maximo=120)
    filas = consultar(
        "SELECT fuente_id, nombre, descripcion, admite_estructura, "
        "       admite_identificadores, activa, motivo "
        "  FROM integracion.fuente ORDER BY fuente_id")
    return responder({
        "total": len(filas),
        "fuentes": [dict(f) for f in filas],
        "nota": "Una fuente no registrada no puede integrar. Lo normal es "
                "aceptar de cualquiera que traiga un token valido, y "
                "entonces cualquier componente con credenciales de la "
                "organizacion puede reescribir el arbol organizacional.",
    }, 200, raiz="fuentes_respuesta")


@app.get(f"{BASE}/ingestas")
@requiere_permiso("IMPORTACION_APLICAR", "BITACORA_CONSULTAR")
def ingestas():
    """El historial, con las rechazadas incluidas.

    Las rechazadas son la mitad del valor de tener una puerta: un intento
    de meter campos de persona que no quedara registrado no habría
    existido nunca.
    """
    limite_consumo(maximo=60)
    filas = consultar(
        "SELECT ingesta_id, fuente_id, tipo, modo, formato, renglones, "
        "       aplicados, errores, advertencias, veredicto, sello_sha256, "
        "       fecha_ingesta FROM integracion.ingesta "
        " ORDER BY fecha_ingesta DESC LIMIT 50")
    datos = []
    for f in filas:
        d = dict(f)
        d["fecha_ingesta"] = d["fecha_ingesta"].isoformat()
        datos.append(d)
    return responder({"total": len(datos), "ingestas": datos},
                     200, raiz="ingestas_respuesta")


@app.get(f"{BASE}/ingestas/<int:ingesta_id>")
@requiere_permiso("IMPORTACION_APLICAR", "BITACORA_CONSULTAR")
def ingesta(ingesta_id):
    """Una ingesta con sus hallazgos, renglón por renglón.

    Quien tiene que arreglar el archivo no es quien opera esta plataforma,
    es el equipo del sistema corporativo. Si el error no dice el renglón y
    el campo, el arreglo pasa por una cadena de correos.
    """
    limite_consumo(maximo=120)
    fila = consultar_uno(
        "SELECT * FROM integracion.ingesta WHERE ingesta_id = %s",
        (ingesta_id,))
    if not fila:
        raise ErrorApi("NO_ENCONTRADO",
                       f"No existe la ingesta {ingesta_id}.", 404)
    hallazgos = consultar(
        "SELECT renglon, campo, codigo, severidad, detalle "
        "  FROM integracion.hallazgo WHERE ingesta_id = %s "
        " ORDER BY severidad, renglon NULLS LAST, hallazgo_id", (ingesta_id,))
    salida = dict(fila)
    salida["fecha_ingesta"] = fila["fecha_ingesta"].isoformat()
    salida["hallazgos"] = [dict(h) for h in hallazgos]
    return responder(salida, 200, raiz="ingesta_respuesta")


@app.get(f"{BASE}/esquema.xsd")
@requiere_token
def esquema():
    """El XSD contra el que se valida, servido por el propio servicio.

    Está aquí para que el equipo del sistema corporativo valide ANTES de
    mandar, en lugar de descubrir los problemas a base de rechazos. Y para
    que el esquema que se publica sea EL MISMO contra el que se valida: si
    se les mandara por correo, las dos copias se separarían y un archivo
    correcto según la copia vieja sería rechazado sin explicación
    entendible.
    """
    limite_consumo(maximo=120)
    ruta = os.path.join(CARPETA_XSD, "integracion.xsd")
    if not os.path.exists(ruta):
        raise ErrorApi("ESQUEMA_NO_DISPONIBLE",
                       "El esquema no esta en este despliegue. La validacion "
                       "contra XSD esta desactivada y las respuestas lo "
                       "dicen en 'validacion_xsd'.", 503)
    from flask import Response
    with open(ruta, encoding="utf-8") as f:
        return Response(f.read(), mimetype="application/xml")


@app.get(f"{BASE}/campos-rechazados")
@requiere_token
def campos_rechazados():
    """La lista de campos que no pueden entrar, publicada.

    Está en el contrato para que el equipo del sistema corporativo pueda
    limpiar su extracción ANTES de mandarla, en lugar de descubrirlo a
    base de rechazos.
    """
    limite_consumo(maximo=120)
    return responder({
        "campos_de_persona_rechazados": sorted(CAMPOS_DE_PERSONA),
        "coincidencia": "por contenido del nombre del campo, sin acentos y "
                        "en minusculas: 'nombre' rechaza tambien "
                        "'nombre_completo' y 'primer_nombre'. Una "
                        "comparacion exacta dejaria pasar casi todos los "
                        "nombres que de verdad usa un sistema corporativo.",
        "campos_admitidos_estructura": sorted(CAMPOS_ESTRUCTURA),
        "campos_admitidos_identificadores": sorted(CAMPOS_IDENTIFICADORES),
        "por_que_rechazo_y_no_silencio":
            "Ignorarlos seria lo comodo y tiene una consecuencia mala: el "
            "sistema de origen sigue mandandolos, nadie se entera, y el dia "
            "que alguien «mejore» el importador para no desperdiciar datos, "
            "ya estan llegando. Un rechazo ruidoso obliga a arreglar el "
            "origen.",
        "segunda_defensa":
            "En XML hay ademas validacion contra integracion.xsd, publicado "
            "en /api/v1/integracion/esquema.xsd. El esquema declara lo "
            "PERMITIDO —los renglones son xs:all cerrado— asi que un campo "
            "no previsto en esta lista tampoco pasa. La lista existe igual "
            "porque cubre el JSON y porque NOMBRA el campo culpable, que es "
            "lo que permite arreglar el origen: un «este elemento no se "
            "esperaba» no le dice al equipo corporativo que tiene que "
            "quitar.",
        "lo_que_nunca_hace":
            "Crear personas. Un identificador externo sin seudonimo "
            "correspondiente es un hallazgo, no un alta: una persona creada "
            "por aqui no tendria consentimiento y podria contar en "
            "agregados sin haber aceptado nada.",
    }, 200, raiz="campos_respuesta")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PUERTO", "8124")))
