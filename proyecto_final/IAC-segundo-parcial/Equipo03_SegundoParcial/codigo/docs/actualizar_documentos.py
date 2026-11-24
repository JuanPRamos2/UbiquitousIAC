#!/usr/bin/env python3
"""Actualiza los documentos .docx con las correcciones del segundo parcial.

POR QUÉ ES UN GUIÓN Y NO UNA EDICIÓN A MANO
--------------------------------------------
Los documentos afirman cifras que el repositorio puede desmentir: cuántos
microservicios hay, cuántas migraciones, cuántas garantías, cuántas
pruebas. La entrega anterior se entregó con esas cifras desfasadas —decía
nueve microservicios cuando ya había más— y eso es justo el tipo de cosa
que hace dudar de todo lo demás.

Con un guión, las cifras se leen del repositorio en el momento de generar
los documentos. Si alguien agrega un servicio y no vuelve a generar, la
prueba `test_los_documentos_no_contradicen_al_repositorio` lo detiene.

Uso:
    python3 docs/actualizar_documentos.py
"""
import copy
import os
import re
import subprocess
import sys

try:
    import docx
except ImportError:
    sys.exit("Falta python-docx: pip install --break-system-packages python-docx")

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(RAIZ, "docs")

NUMEROS = {8: "ocho", 9: "nueve", 10: "diez", 11: "once", 12: "doce",
           13: "trece", 14: "catorce", 15: "quince", 16: "dieciséis",
           17: "diecisiete", 18: "dieciocho", 19: "diecinueve",
           20: "veinte", 6: "seis", 7: "siete",
           21: "veintiuno", 22: "veintidós", 23: "veintitrés",
           24: "veinticuatro", 25: "veinticinco", 26: "veintiséis",
           27: "veintisiete", 28: "veintiocho", 29: "veintinueve",
           30: "treinta"}


# =========================================================================
# Los hechos, leídos del repositorio
# =========================================================================
def servicios():
    """Los servicios reales, con su puerto leído del compose.

    El puerto sale de `docker-compose.yml` y no de un `app.py`, por dos
    motivos. Uno: los dos servicios de Node no tienen `app.py`. Dos, y es
    el que importa: el puerto que el manual documenta es el PUBLICADO, el
    que alguien escribe en el navegador, y ese lo decide el compose —
    dentro de la red interna los dieciséis escuchan en 8000.

    El primer intento lo sacaba con una expresión regular sobre el texto
    del compose, y daba puertos de otro servicio: el nombre de cada
    servicio también aparece en las variables de ambiente del portal, así
    que la búsqueda empezaba en el lugar equivocado. Con un parser de YAML
    no hay nada que adivinar.
    """
    import yaml
    base = os.path.join(RAIZ, "apps", "microservicios")
    compose = yaml.safe_load(
        open(os.path.join(RAIZ, "docker-compose.yml"), encoding="utf-8"))
    publicados = {}
    for nombre, definicion in (compose.get("services") or {}).items():
        for puerto in (definicion or {}).get("ports") or []:
            publicados[nombre] = str(puerto).split(":")[0]

    salida = []
    for nombre in sorted(os.listdir(base)):
        carpeta = os.path.join(base, nombre)
        if not os.path.isdir(carpeta) or nombre in ("comun", "comun-node"):
            continue
        lenguaje = ("Node" if os.path.exists(
            os.path.join(carpeta, "package.json")) else "Python")
        salida.append({"nombre": nombre,
                       "puerto": publicados.get(nombre, "?"),
                       "lenguaje": lenguaje})
    sin_puerto = [s["nombre"] for s in salida if s["puerto"] == "?"]
    if sin_puerto:
        raise SystemExit(
            f"Estos servicios existen y el compose no los publica: "
            f"{sin_puerto}. Un servicio que no esta en el compose no se "
            f"levanta, y el manual estaria documentando algo que no corre.")
    return salida


def migraciones():
    carpeta = os.path.join(RAIZ, "db", "migraciones")
    return sorted(f for f in os.listdir(carpeta) if f.endswith(".sql"))


def garantias():
    """Las garantías declaradas, leídas del SQL y no de la base.

    Del SQL a propósito: el guión tiene que poder correr sin PostgreSQL
    levantado, y lo que los documentos afirman es lo que el repositorio
    declara, no lo que una base concreta tenga aplicado.
    """
    codigos = set()
    for carpeta in (os.path.join(RAIZ, "db", "esquema"),
                    os.path.join(RAIZ, "db", "migraciones")):
        for archivo in sorted(os.listdir(carpeta)):
            if not archivo.endswith(".sql"):
                continue
            texto = open(os.path.join(carpeta, archivo),
                         encoding="utf-8").read()
            codigos |= set(re.findall(r"'(G\d) ", texto))
    return sorted(codigos)


def cuenta_pruebas():
    """Las pruebas que recoge pytest, sin ejecutarlas."""
    try:
        salida = subprocess.run(
            [sys.executable, "-m", "pytest", "pruebas/", "--collect-only",
             "-q", "-p", "no:randomly"],
            cwd=RAIZ, capture_output=True, text=True, timeout=180).stdout
        m = re.search(r"(\d+)\s+tests? collected", salida)
        if m:
            return int(m.group(1))
        return len([l for l in salida.splitlines() if "::" in l])
    except Exception:
        return None


# =========================================================================
# Utilidades de edición
# =========================================================================
def reemplazar_en_parrafo(parrafo, cambios):
    """Reemplaza texto conservando el formato del primer `run`.

    Word parte un párrafo en `runs` por motivos de formato, y un texto
    buscado puede caer partido entre dos. Por eso se reescribe el párrafo
    completo en su primer run y se vacían los demás: es lo único que
    funciona de forma fiable, y el formato del párrafo se conserva porque
    el primer run lo lleva.
    """
    original = parrafo.text
    nuevo = original
    for viejo, reemplazo in cambios:
        nuevo = nuevo.replace(viejo, reemplazo)
    if nuevo == original or not parrafo.runs:
        return False
    parrafo.runs[0].text = nuevo
    for run in parrafo.runs[1:]:
        run.text = ""
    return True


def clonar_tabla(documento, modelo, filas):
    """Agrega una tabla con el formato de otra ya existente.

    Se clona el XML de una tabla del documento en lugar de aplicar un
    estilo por nombre: estos documentos no usan estilos de tabla con
    nombre, así que un `add_table` saldría sin bordes ni sombreado y se
    notaría al lado de las demás.
    """
    nueva = copy.deepcopy(modelo._tbl)
    documento.element.body.append(nueva)
    tabla = documento.tables[-1]

    # Se dejan tantas filas como haga falta, clonando la última.
    while len(tabla.rows) > len(filas):
        tabla._tbl.remove(tabla.rows[-1]._tr)
    while len(tabla.rows) < len(filas):
        tabla._tbl.append(copy.deepcopy(tabla.rows[-1]._tr))

    for fila, valores in zip(tabla.rows, filas):
        # Si la fila destino tiene menos celdas que valores, se recortan:
        # vale más una tabla coherente que una fila desbordada.
        for celda, valor in zip(fila.cells, valores):
            parrafo = celda.paragraphs[0]
            if parrafo.runs:
                parrafo.runs[0].text = str(valor)
                for run in parrafo.runs[1:]:
                    run.text = ""
            else:
                parrafo.add_run(str(valor))
    return tabla


def estilo_de(documento, nombre):
    """El objeto de estilo, buscado recorriendo la colección.

    `documento.styles["Heading 1"]` lanza KeyError en estos archivos
    aunque el estilo exista: su nombre interno es el de OOXML («heading
    1») y la traducción de python-docx no lo encuentra. Recorrer la
    colección y comparar el nombre que ya reportan los párrafos sí
    funciona, y es lo que mantiene los títulos nuevos con el mismo formato
    que los viejos.
    """
    for estilo in documento.styles:
        if estilo.name == nombre:
            return estilo
    return None


def agregar(documento, texto, estilo="Normal"):
    p = documento.add_paragraph(texto)
    obj = estilo_de(documento, estilo)
    if obj is not None:
        p.style = obj
    return p


# =========================================================================
# El contenido nuevo, común a los tres documentos
# =========================================================================
def seccion_de_correcciones(d, numero, modelo_tabla, datos):
    """La sección que responde a la retroalimentación del profesor."""
    agregar(d, f"{numero}. Las correcciones de este entregable", "Heading 1")

    agregar(d,
            "La revisión del segundo parcial señaló tres cosas: que la "
            "entrega no se veía revisada, que había afirmaciones sin "
            "sustento y que cada integrante debe poder sostener sus "
            "componentes sin ayuda. Esta sección registra qué se corrigió "
            "y qué se encontró al hacerlo. Está escrita en pasado y con "
            "nombres concretos a propósito: una lista de mejoras en "
            "abstracto es exactamente lo que no se puede defender.")

    agregar(d, f"{numero}.1 El reparto, por integrante", "Heading 2")
    agregar(d,
            "Cada componente tiene un responsable único, y el responsable "
            "es quien lo escribió y quien lo defiende. Donde antes decía "
            "«Consultas» o «Reportes» sin nombre, ahora hay un nombre.")
    clonar_tabla(d, modelo_tabla, datos["reparto"])

    agregar(d, f"{numero}.2 Los defectos que encontraron las pruebas",
            "Heading 2")
    agregar(d,
            "Todos los de esta lista los destapó una prueba escrita contra "
            "el componente, no una lectura del código. Se enumeran con su "
            "consecuencia porque un defecto sin consecuencia escrita no se "
            "distingue de una preferencia de estilo.")
    clonar_tabla(d, modelo_tabla, datos["defectos"])

    agregar(d, f"{numero}.3 Lo que se quitó", "Heading 2")
    agregar(d,
            "Quitar funcionalidad era parte explícita de lo pedido. Lo que "
            "se quitó y por qué:")
    clonar_tabla(d, modelo_tabla, datos["quitado"])

    agregar(d, f"{numero}.4 Las dos decisiones opuestas, y por qué",
            "Heading 2")
    agregar(d,
            "sync-service e integration-service resuelven el mismo "
            "problema —recibir datos de fuera— y deciden al contrario "
            "sobre lo mismo: el primero aplica un lote a medias, renglón "
            "por renglón; el segundo es todo o nada. Conviene tenerlo "
            "claro porque es lo primero que parece una incoherencia.")
    agregar(d,
            "El motivo es la naturaleza de lo que llega. Un lote de "
            "cuarenta autoreportes con uno mal formado, aplicado a medias, "
            "son treinta y nueve respuestas guardadas: un resultado útil, y "
            "el cliente que las capturó sin red no tiene cómo recuperarlas "
            "si se rechazan en bloque. Un árbol organizacional aplicado a "
            "medias son unidades huérfanas, y el alcance de todos los "
            "perfiles se calcula recorriendo ese árbol: un árbol roto "
            "significa gente viendo datos de áreas que no le tocan, o no "
            "viendo los suyos.")

    agregar(d, f"{numero}.5 Las dos garantías nuevas", "Heading 2")
    agregar(d,
            "Las migraciones 011 y 012 abrieron dos vías de entrada "
            "nuevas, y durante un rato ninguna garantía las miraba. La 013 "
            "agrega G7 y G8, que comprueban contra el catálogo del sistema "
            "que esas vías no tienen dónde guardar un dato de persona.")
    agregar(d,
            "La diferencia con el filtro del servicio importa. "
            "integration-service ya rechaza los campos de persona que "
            "lleguen en un archivo, pero ese filtro protege de lo que "
            "entra por su API. La garantía comprueba que no haya dónde "
            "ponerlos, y es la que sigue valiendo el día que alguien "
            "agregue una columna «para depurar»: el filtro seguiría "
            "funcionando igual, y la columna ya estaría ahí. Es el mismo "
            "razonamiento de G1, que existe desde el primer parcial.")
    clonar_tabla(d, modelo_tabla, datos["garantias_nuevas"])


# =========================================================================
# Los datos de la sección
# =========================================================================
def datos_de_correcciones(svc):
    por_nombre = {s["nombre"]: s["puerto"] for s in svc}

    reparto = [["Integrante", "Componentes", "Puertos"]]
    reparto.append([
        "Emiliano Pascual Piñales Sánchez #657657",
        "queries-service, reports-service, algorithms-service, "
        "trends-service, interventions-service, export-service",
        ", ".join(por_nombre.get(n, "?") for n in
                  ("queries-service", "reports-service", "algorithms-service",
                   "trends-service", "interventions-service",
                   "export-service"))])
    reparto.append([
        "Gerardo Quiroga Ramírez #650313",
        "documents-service, notifications-service, sync-service, "
        "configuration-service, monitoring-service, integration-service",
        ", ".join(por_nombre.get(n, "?") for n in
                  ("documents-service", "notifications-service",
                   "sync-service", "configuration-service",
                   "monitoring-service", "integration-service"))])

    defectos = [["Dónde", "Qué estaba mal", "Qué habría pasado"]]
    defectos += [
        ["sync-service",
         "La respuesta se registraba con una consulta sin COMMIT, así que "
         "la transacción se deshacía al salir.",
         "El servicio contestaba APLICADA y no quedaba nada guardado. El "
         "cliente borraba su copia local de una respuesta que nunca se "
         "escribió. Lo destapó la prueba del conflicto: la segunda "
         "respuesta del mismo seudónimo a la misma campaña también salía "
         "APLICADA."],
        ["integration-service",
         "El filtro de campos de persona coincidía por contenido del "
         "nombre, y «nombre» también coincide con nombre_unidad.",
         "Se rechazaba todo archivo de estructura bien formado. Se "
         "corrigió invirtiendo el orden: la lista blanca de campos "
         "necesarios gana sobre la negra, que solo juzga lo que llegó de "
         "más."],
        ["integration-service",
         "La lista de tipos de unidad estaba escrita a mano y había "
         "quedado distinta de la restricción de la base: sobraban dos "
         "tipos y faltaba uno.",
         "El servicio validaba el archivo, lo declaraba correcto y "
         "reventaba al insertar. Como aplicar es todo o nada, el archivo "
         "entero fallaba con un mensaje que no decía qué campo era. Ahora "
         "los tipos se leen de la propia restricción."],
        ["integration-service",
         "Consultaba consentimiento.seudonimo, que el rol de la "
         "aplicación no puede leer.",
         "Fallaba con «permission denied», que es la garantía del "
         "proyecto funcionando: esa tabla vincula seudónimo con empleado. "
         "Se cambió por la vista de consentimiento vigente, que además es "
         "la fuente correcta por el fondo del asunto."],
        ["interventions-service",
         "Leía el identificador devuelto por RETURNING por posición, y el "
         "cursor del proyecto devuelve diccionarios.",
         "Error 500 al crear cualquier plan."],
        ["interventions-service",
         "No contemplaba la restricción única de una evaluación por plan.",
         "La segunda evaluación salía 500 con el texto de PostgreSQL "
         "asomando en la respuesta. Ahora responde 409 y explica que el "
         "límite es deliberado: si se pudiera repetir con otro par de "
         "campañas, bastaría probar pares hasta encontrar el que deja bien "
         "a la intervención."],
        ["integracion.fn_validar_arbol_propuesto",
         "Una unidad que se declaraba su propio padre producía dos "
         "hallazgos de ciclo.",
         "Un informe que repite hallazgos hace dudar de la cuenta de "
         "errores. El recorrido recursivo generaba una cadena infinita "
         "con un auto-padre; ahora se excluye de ese recorrido."],
        ["Las pruebas propias",
         "Tomaban siempre el mismo seudónimo, y consultaban tablas que el "
         "rol de la aplicación no puede leer.",
         "Pasaban solas y fallaban al correr la suite dos veces. Las "
         "pruebas ahora se someten a las mismas restricciones que los "
         "servicios: si usaran una vía privilegiada, comprobarían algo "
         "que en producción no pasa."],
        ["docker-compose.yml y el compose base",
         "No montaban las migraciones nuevas.",
         "Una base creada con esos archivos levanta y falla al primer uso "
         "real, y la sonda de salud no lo detecta. Lo detectó una prueba "
         "que ya existía para eso."],
        ["scripts/arrancar_microservicios.sh",
         "Su lista de servicios se había quedado corta.",
         "El manual manda correr ese guión, y tal como estaba no levantaba "
         "los servicios nuevos."],
        ["monitoring-service",
         "`cursor` no estaba importado, y el try del registro se tragaba "
         "el NameError.",
         "La supervision de reinicios funcionaba en pantalla y no guardaba "
         "nada. Es el modo de falla de la migracion 007 otra vez: el "
         "registro va envuelto en un try para no tumbar la peticion, asi "
         "que su fallo no se ve. El logger.error original tampoco mostraba "
         "el motivo; ahora es logger.exception."],
        ["monitoring-service",
         "Le faltaban dos funcionalidades de la tabla del profesor: "
         "alertas y supervision de contenedores.",
         "Salio al cotejar la tabla renglon por renglon, no antes. Se "
         "agregaron /monitoreo/alertas con ocho reglas y "
         "/monitoreo/contenedores, que detecta reinicios comparando la "
         "identidad de instancia que cada servicio reporta en "
         "/health/live: un contenedor en bucle de reinicio pasa TODAS las "
         "sondas de salud."],
        ["interventions-service",
         "Registraba el cambio de estado y el avance con "
         "INTERVENCION_SEGUIMIENTO, que es un PERMISO y no una accion de "
         "bitacora.",
         "Ni un cambio de estado ni un avance quedaban registrados. El "
         "ciclo de aprobacion esta declarado para poder auditarlo, asi que "
         "sin rastro la maquina de estados solo impide saltos y no deja "
         "constancia de los pasos que si se dieron. Migracion 015, con dos "
         "acciones separadas: mover un plan y reportar un avance son "
         "hechos distintos."],
        ["La prueba que debia atrapar lo anterior",
         "Buscaba el codigo en el texto de las migraciones, y la cadena si "
         "aparecia ahi: como permiso.",
         "Daba por bueno un codigo que auditoria.tipo_accion no tenia. Es la tercera vez que este modo de falla aparece en el proyecto (007, 014 y "
         "015), asi que ahora la prueba comprueba contra los INSERT a esa "
         "tabla y no contra el texto completo del SQL."],
        ["integration-service",
         "El renglon #24 de la tabla pide validacion XSD y el servicio "
         "aceptaba XML sin validarlo contra ningun esquema.",
         "Un archivo del sistema corporativo con elementos no previstos "
         "entraba hasta el codigo que interpreta renglones. Ahora existe "
         "contratos/xml/integracion.xsd, se valida ANTES de leer el "
         "contenido, y el esquema se publica en /esquema.xsd para que el "
         "equipo corporativo valide antes de mandar. El esquema declara lo "
         "PERMITIDO, asi que atrapa campos que la lista negra del servicio "
         "no previo."],
        ["queries-service",
         "El renglon #07 pide consultas por campania, PERIODO y unidad, y "
         "la serie de tendencia no se podia acotar.",
         "Se agregaron desde_campania y hasta_campania, que cortan por "
         "secuencia y no por el texto del identificador: ordenar como "
         "cadena pondria CAMP-2026-S10 antes que CAMP-2026-S2. El rango "
         "entra en la clave de cache, porque si no la primera consulta "
         "dejaria guardada la serie completa y la siguiente, acotada, "
         "recibiria esa misma serie entera desde la cache: el filtro "
         "pareceria no funcionar y nadie sabria por que."],
    ]

    quitado = [["Qué se quitó", "De dónde", "Por qué"]]
    quitado += [
        ["La sección de limitaciones no verificadas",
         "El manual y el documento general",
         "Afirmaba cosas sobre el entorno en lugar de sobre el sistema. Lo "
         "que no se pudo comprobar se dejó de afirmar, en los dos "
         "sentidos."],
        ["El manejo de archivos de evidencia",
         "El portal web",
         "Vivía en la capa equivocada: el portal validaba firmas, "
         "calculaba hashes y escribía en el almacén. Se movió a "
         "documents-service, que es el responsable del recurso, y el "
         "portal quedó delegando."],
        ["La lista de tipos de unidad escrita a mano",
         "integration-service",
         "Una copia al lado de una restricción de la base se separa de "
         "ella en algún momento, y la separación solo se ve al insertar."],
        ["El estado SIN_DATOS_SUFICIENTES como valor almacenable",
         "interventions-service",
         "No es una conclusión: es la ausencia de una. Guardarlo cerraría "
         "el plan sin haberlo evaluado nunca, porque solo se admite una "
         "evaluación por plan."],
    ]

    garantias_nuevas = [["Garantía", "Qué comprueba", "Por qué"]]
    garantias_nuevas += [
        ["G7 Integración sin datos de persona",
         "Que ninguna tabla del esquema integracion tenga columna para un "
         "nombre, un correo, un RFC, un sueldo, un puesto o una fecha de "
         "nacimiento.",
         "integration-service se conecta a un sistema que tiene todo eso "
         "de toda la organización. La vía de integración es por donde "
         "entrarían, y casi siempre entran sin que nadie lo decida."],
        ["G8 Sincronización sin identidad",
         "Que ninguna tabla del esquema sincronizacion contenga "
         "empleado_id.",
         "Un empleado_id junto al campania_id y al resultado sería un "
         "vínculo persona-respuesta-campaña en una tabla que el rol de la "
         "aplicación lee sin restricción: justo lo que G2 evita en "
         "autoreporte."],
    ]
    return {"reparto": reparto, "defectos": defectos, "quitado": quitado,
            "garantias_nuevas": garantias_nuevas}


# =========================================================================
# Los tres documentos
# =========================================================================
def comunes(n_svc, n_mig, n_gar, n_pruebas, n_python=None):
    """Reemplazos de cifras, aplicables a todos los documentos.

    La lista es larga y explícita a propósito. Un reemplazo genérico de
    «nueve» por «dieciséis» tocaría frases donde «nueve» es correcto —los
    nueve esquemas XSD, por ejemplo— y el documento quedaría peor que
    antes. Cada entrada de aquí es una frase concreta que alguien escribió
    y que dejó de ser cierta.
    """
    n_python = n_python if n_python is not None else n_svc - 2
    cambios = [
        # Frases concretas, con su sustantivo, que afirmaban un conteo.
        ("Nueve microservicios", f"{NUMEROS[n_svc].capitalize()} microservicios"),
        ("Portal web, siete microservicios",
         f"Portal web, {NUMEROS[n_svc]} microservicios"),
        ("Nueve servicios con su estado",
         f"{NUMEROS[n_svc].capitalize()} servicios con su estado"),
        ("los seis servicios en Python",
         f"los {NUMEROS[n_python]} servicios en Python"),
        ("Siete servicios están en Python",
         f"{NUMEROS[n_python].capitalize()} servicios están en Python"),
        ("Cinco cosas son idénticas en los",
         "Cinco cosas son idénticas en los"),
        ("los nueve microservicios", f"los {NUMEROS[n_svc]} microservicios"),
        ("Los nueve microservicios", f"Los {NUMEROS[n_svc]} microservicios"),
        ("los nueve servicios", f"los {NUMEROS[n_svc]} servicios"),
        ("Los nueve servicios", f"Los {NUMEROS[n_svc]} servicios"),
        ("Nueve servicios,", f"{NUMEROS[n_svc].capitalize()} servicios,"),
        ("nueve microservicios", f"{NUMEROS[n_svc]} microservicios"),
        ("los ocho servicios", f"los {NUMEROS[n_svc]} servicios"),
        ("Los ocho servicios", f"Los {NUMEROS[n_svc]} servicios"),
        ("en los ocho servicios", f"en los {NUMEROS[n_svc]} servicios"),
        ("ocho servicios,", f"{NUMEROS[n_svc]} servicios,"),
        ("ocho microservicios", f"{NUMEROS[n_svc]} microservicios"),
        ("Dieciséis servicios", f"{NUMEROS[n_svc].capitalize()} servicios"),
        ("Catorce servicios", f"{NUMEROS[n_python].capitalize()} servicios"),
        ("Veintidós servicios", f"{NUMEROS[n_python].capitalize()} servicios"),
        ("veintidós servicios", f"{NUMEROS[n_python]} servicios"),
        ("levanta veinte servicios", f"levanta {NUMEROS[n_svc + 4]} servicios"),
        ("veinte servicios", f"{NUMEROS[n_svc + 4]} servicios"),
        ("los dieciséis microservicios", f"los {NUMEROS[n_svc]} microservicios"),
        ("Los dieciséis microservicios", f"Los {NUMEROS[n_svc]} microservicios"),
        ("dieciséis microservicios", f"{NUMEROS[n_svc]} microservicios"),
        ("Dieciséis microservicios", f"{NUMEROS[n_svc].capitalize()} microservicios"),
        ("los dieciséis servicios", f"los {NUMEROS[n_svc]} servicios"),
        ("Los dieciséis servicios", f"Los {NUMEROS[n_svc]} servicios"),
        ("dieciséis servicios", f"{NUMEROS[n_svc]} servicios"),
        ("catorce servicios", f"{NUMEROS[n_python]} servicios"),
        ("las quince migraciones", f"las {NUMEROS[n_mig]} migraciones"),
        ("quince migraciones", f"{NUMEROS[n_mig]} migraciones"),
        ("dieciséis migraciones", f"{NUMEROS[n_mig]} migraciones"),
        ("las dieciséis migraciones", f"las {NUMEROS[n_mig]} migraciones"),
        ("levanta trece servicios", f"levanta {NUMEROS[n_svc + 4]} servicios"),
        ("las seis migraciones", f"las {NUMEROS[n_mig]} migraciones"),
        ("Las seis garantías", f"Las {NUMEROS[n_gar]} garantías"),
        ("las seis garantías", f"las {NUMEROS[n_gar]} garantías"),
        ("Las seis garantias", f"Las {NUMEROS[n_gar]} garantías"),
        ("las seis garantias", f"las {NUMEROS[n_gar]} garantías"),
    ]
    if n_pruebas:
        cambios += [(f"{v} pruebas", f"{n_pruebas} pruebas")
                    for v in ("204", "231", "280", "320", "393", "397", "499")
                    if str(n_pruebas) != v]
    return cambios


def main():
    svc = servicios()
    mig = migraciones()
    gar = garantias()
    n_pruebas = cuenta_pruebas()
    print(f"Repositorio: {len(svc)} servicios, {len(mig)} migraciones, "
          f"{len(gar)} garantias, {n_pruebas} pruebas")

    n_python = sum(1 for x in svc if x["lenguaje"] == "Python")
    cambios = comunes(len(svc), len(mig), len(gar), n_pruebas,
                      n_python)
    datos = datos_de_correcciones(svc)

    RESPONSABILIDAD = {
        "auth-service": "Emitir, renovar, validar y revocar tokens",
        "users-service": "Usuarios, perfiles, permisos y alcance",
        "catalog-service": "Unidades, instrumentos, versiones, reactivos y "
                           "campanas",
        "main-process-service": "Responder una campana y pedir apoyo",
        "documents-service": "Evidencias, avisos versionados y archivos",
        "notifications-service": "Notificaciones internas",
        "queries-service": "Lectura de resultados publicados, con cache",
        "reports-service": "Generar, sellar y entregar reportes",
        "algorithms-service": "Motor de reglas de riesgo sobre lo publicado",
        "trends-service": "Distinguir un cambio real de un movimiento del "
                          "ruido",
        "interventions-service": "Planes organizacionales, seguimiento y "
                                 "evaluacion",
        "sync-service": "Sincronizacion idempotente con red intermitente",
        "export-service": "Egreso controlado de agregados, con bitacora",
        "configuration-service": "Parametros, umbrales k y presupuestos de "
                                 "privacidad",
        "monitoring-service": "Salud, latencia y errores de los demas",
        "integration-service": "Puerta controlada hacia el sistema "
                               "corporativo",
        "consent-service": "Aviso, otorgamiento y revocacion sin borrar",
        "privacy-service": "Seudonimizacion y umbral k, sin calcular ruido",
        "survey-service": "Cuestionario versionado y una respuesta por campania",
        "indicators-service": "Indicadores ya publicados, sin promedio crudo",
        "support-service": "Solicitudes de apoyo contra el seudonimo",
        "organizational-service": "Arbol organizacional y tamano minimo",
        "audit-service": "Bitacora de accesos y correlacion",
        "data-governance-service": "Minimizacion, retencion y baja sin borrado",
    }
    FORMATO = {"catalog-service": "JSON y XML",
               "main-process-service": "JSON y XML"}

    filas_servicios = [["Servicio", "Responsable", "Lenguaje", "Puerto"]]
    responsables = {
        "auth-service": "Integrante 1", "users-service": "Integrante 1",
        "catalog-service": "Integrante 2",
        "main-process-service": "Integrante 2",
        "documents-service": "Gerardo", "notifications-service": "Gerardo",
        "sync-service": "Gerardo", "configuration-service": "Gerardo",
        "monitoring-service": "Gerardo", "integration-service": "Gerardo",
        "queries-service": "Emiliano", "reports-service": "Emiliano",
        "algorithms-service": "Emiliano", "trends-service": "Emiliano",
        "interventions-service": "Emiliano", "export-service": "Emiliano",
        "consent-service": "Juan Pablo", "privacy-service": "Juan Pablo",
        "audit-service": "Juan Pablo", "data-governance-service": "Juan Pablo",
        "survey-service": "Ricardo", "indicators-service": "Ricardo",
        "support-service": "Ricardo", "organizational-service": "Ricardo",
    }
    for s in sorted(svc, key=lambda x: x["puerto"] or "9999"):
        filas_servicios.append([s["nombre"],
                                responsables.get(s["nombre"], "—"),
                                s["lenguaje"], s["puerto"]])

    trabajos = {
        "Manual_Tecnico_y_Demostracion_Equipo03": 9,
        "Reporte_Tecnico_Integrado_Equipo03": 15,
        "Modulo_Microservicios_Completo_Equipo03": 10,
        "Monorepo_y_Ambientes_Equipo03": None,
    }

    for nombre, numero_seccion in trabajos.items():
        ruta = os.path.join(DOCS, f"{nombre}.docx")
        if not os.path.exists(ruta):
            print(f"  (no existe) {nombre}")
            continue
        d = docx.Document(ruta)

        tocados = sum(reemplazar_en_parrafo(p, cambios) for p in d.paragraphs)
        for t in d.tables:
            for fila in t.rows:
                for celda in fila.cells:
                    for p in celda.paragraphs:
                        tocados += reemplazar_en_parrafo(p, cambios)

        # La tabla de servicios se reescribe completa donde exista.
        reescritas = 0
        for t in d.tables:
            cabecera = [c.text.strip().lower() for c in t.rows[0].cells]
            if cabecera[:2] == ["servicio", "responsable"]:
                filas = [f[:len(t.columns)] for f in filas_servicios]
                if len(t.columns) == 5:
                    # La quinta columna es la responsabilidad. Se toma la
                    # que ya estaba cuando existe —es la redaccion que
                    # alguien reviso— y la de la tabla de arriba para los
                    # servicios nuevos.
                    previas = {fila.cells[0].text.strip():
                               fila.cells[4].text.strip()
                               for fila in t.rows[1:]}
                    filas = [f + [previas.get(f[0]) or
                                  RESPONSABILIDAD.get(f[0], "")]
                             for f in filas_servicios]
                    filas[0][4] = "Responsabilidad única"
                clonar_tabla(d, t, filas)
                # La nueva queda al final del documento; se mueve al lugar
                # de la vieja y se borra la vieja.
                nueva = d.tables[-1]
                t._tbl.addnext(nueva._tbl)
                t._tbl.getparent().remove(t._tbl)
                reescritas += 1

        # Las otras dos formas de tabla que listan servicios.
        for t in list(d.tables):
            cabecera = [c.text.strip().lower() for c in t.rows[0].cells]
            if cabecera == ["componente", "puerto", "formato que habla"]:
                filas = [["Componente", "Puerto", "Formato que habla"],
                         ["Portal web", "8000",
                          "HTML (consume JSON de los servicios)"]]
                for x in sorted(svc, key=lambda y: y["puerto"]):
                    filas.append([x["nombre"], x["puerto"],
                                  FORMATO.get(x["nombre"], "JSON y XML")])
                clonar_tabla(d, t, filas)
                nueva = d.tables[-1]
                t._tbl.addnext(nueva._tbl)
                t._tbl.getparent().remove(t._tbl)
                reescritas += 1
            elif cabecera == ["servicio", "única responsabilidad"]:
                filas = [["Servicio", "Única responsabilidad"]]
                previas = {f.cells[0].text.strip(): f.cells[1].text.strip()
                           for f in t.rows[1:]}
                for x in sorted(svc, key=lambda y: y["puerto"]):
                    filas.append([x["nombre"],
                                  previas.get(x["nombre"]) or
                                  RESPONSABILIDAD.get(x["nombre"], "")])
                clonar_tabla(d, t, filas)
                nueva = d.tables[-1]
                t._tbl.addnext(nueva._tbl)
                t._tbl.getparent().remove(t._tbl)
                reescritas += 1

        if numero_seccion:
            modelo = next((t for t in d.tables if len(t.columns) == 3),
                          d.tables[0])
            seccion_de_correcciones(d, numero_seccion, modelo, datos)

        d.save(ruta)
        print(f"  {nombre}: {tocados} textos, {reescritas} tablas de "
              f"servicios, seccion {numero_seccion or '—'}")

    print("\nListo. Para regenerar los PDF:")
    print("  soffice --headless --convert-to pdf --outdir docs docs/*.docx")


if __name__ == "__main__":
    main()
