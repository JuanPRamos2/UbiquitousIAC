"""
Cliente XML de la aplicación de escritorio.

Esta capa es la que habla con los microservicios, y está separada de la
interfaz a propósito: así se puede probar sin abrir una ventana, que es lo
que permite que la suite la verifique en una máquina sin pantalla.

LA REGLA DE LA APLICACIÓN: SOLO XML
-----------------------------------
Todas las peticiones piden `Accept: application/xml` y todas las respuestas
se validan contra el esquema XSD correspondiente antes de que la interfaz
las vea. No hay un camino alterno en JSON, ni siquiera para el inicio de
sesión: el parcial pide que la aplicación de escritorio consuma
exclusivamente XML, y tener una vía en JSON «por si acaso» haría que esa
afirmación dejara de ser verificable.

POR QUÉ SE VALIDA CONTRA EL XSD EN EL CLIENTE
---------------------------------------------
El servicio ya valida lo que recibe. Validar lo que llega es otra cosa:
protege a la aplicación de una versión del servicio que cambió un campo sin
avisar. Si llega un documento que no cumple el contrato, la aplicación lo
dice con el error del validador en lugar de mostrar una tabla a la que le
faltan columnas, o peor, de interpretar un valor nulo como un cero.

Esa distinción importa aquí más que en otros proyectos: un agregado
suprimido por el umbral de privacidad viaja con `xsi:nil="true"`, y un
cliente que lo tratara como cadena vacía mostraría 0.00 —la peor unidad de
la empresa— donde el sistema quiso decir «no hay dato publicable».
"""
import os
import urllib.error
import urllib.parse
import urllib.request

from lxml import etree

ESPACIO = "http://nexum.com.mx/bienestar/v1"
XSI = "http://www.w3.org/2001/XMLSchema-instance"

# Carpeta de los esquemas. Son los MISMOS archivos que usan los servicios y
# la suite de pruebas: si se copiaran aquí, las dos copias se separarían.
CARPETA_XSD = os.environ.get(
    "CONTRATOS_XSD",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "contratos", "xml"))

SERVICIOS = {
    "auth": os.environ.get("AUTH_SERVICE_URL", "http://127.0.0.1:8101"),
    "usuarios": os.environ.get("USERS_SERVICE_URL", "http://127.0.0.1:8102"),
    "catalogos": os.environ.get("CATALOG_SERVICE_URL", "http://127.0.0.1:8103"),
    "proceso": os.environ.get("MAIN_PROCESS_SERVICE_URL", "http://127.0.0.1:8104"),
    "documentos": os.environ.get("DOCUMENTS_SERVICE_URL", "http://127.0.0.1:8105"),
    "consultas": os.environ.get("QUERIES_SERVICE_URL", "http://127.0.0.1:8107"),
    "reportes": os.environ.get("REPORTS_SERVICE_URL", "http://127.0.0.1:8108"),
    "algoritmos": os.environ.get("ALGORITHMS_SERVICE_URL", "http://127.0.0.1:8109"),
}

TIEMPO_LIMITE = float(os.environ.get("ESCRITORIO_TIMEOUT", "15"))

_esquemas = {}


def esquema(nombre):
    """Compila un XSD una sola vez y lo reutiliza.

    Compilarlo en cada respuesta costaría decenas de milisegundos por
    petición, y con una tabla que se recarga al filtrar eso se nota.
    """
    if nombre not in _esquemas:
        ruta = os.path.join(CARPETA_XSD, nombre)
        if not os.path.exists(ruta):
            raise ErrorCliente(
                "CONTRATO_AUSENTE",
                f"No se encontro el esquema {nombre} en {CARPETA_XSD}. La "
                f"aplicacion valida toda respuesta contra el contrato del "
                f"equipo y no funciona sin esos archivos.")
        # Se parsea desde su carpeta para que xs:include resuelva comun.xsd.
        _esquemas[nombre] = etree.XMLSchema(etree.parse(ruta))
    return _esquemas[nombre]


class ErrorCliente(Exception):
    """Un error que la interfaz puede mostrar tal cual.

    Trae el código estable del servicio cuando viene de un sobre de error,
    de modo que la ventana pueda decidir qué hacer (reintentar, pedir
    sesión de nuevo, avisar) sin leer el mensaje, que puede cambiar de
    redacción.
    """

    def __init__(self, codigo, mensaje, http=None, detalles=None):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.http = http
        self.detalles = detalles or []

    def __str__(self):
        base = f"[{self.codigo}] {self.mensaje}"
        if self.detalles:
            base += "\n" + "\n".join(
                f"  · {d.get('campo')}: {d.get('problema')}" for d in self.detalles)
        return base


def _texto(nodo, etiqueta, por_omision=None):
    """Lee un hijo, distinguiendo nil de cadena vacía.

    Devuelve None cuando el elemento viene con xsi:nil, y la cadena vacía
    cuando viene vacío de verdad. Esa diferencia es la que separa «no hay
    dato publicable» de «el dato es vacio», y en este proyecto decide si la
    tabla muestra un guión o un cero.
    """
    hijo = nodo.find(f"{{{ESPACIO}}}{etiqueta}")
    if hijo is None:
        return por_omision
    if hijo.get(f"{{{XSI}}}nil") == "true":
        return None
    return hijo.text if hijo.text is not None else ""


def a_diccionario(nodo):
    """Convierte un elemento XML en un diccionario plano o anidado."""
    hijos = list(nodo)
    if not hijos:
        if nodo.get(f"{{{XSI}}}nil") == "true":
            return None
        return nodo.text if nodo.text is not None else ""
    salida = {}
    for hijo in hijos:
        nombre = etree.QName(hijo).localname
        valor = a_diccionario(hijo)
        if nombre in salida:
            if not isinstance(salida[nombre], list):
                salida[nombre] = [salida[nombre]]
            salida[nombre].append(valor)
        else:
            salida[nombre] = valor
    return salida


def lista_de(nodo, plural, singular):
    """Extrae una lista envuelta en plural con hijos en singular.

    Devuelve None cuando la ENVOLTURA no viene y [] cuando viene vacía. La
    distinción es la misma que entre xsi:nil y la cadena vacía, y sirve
    para lo mismo: «no hay detecciones en esta campaña» es un hallazgo;
    «el servicio no mandó esa sección» es un contrato distinto del que se
    esperaba, y conviene que se note en lugar de verse como una lista
    vacía.

    Quien solo quiera recorrerla escribe `lista_de(...) or []`.
    """
    envoltura = nodo.find(f"{{{ESPACIO}}}{plural}")
    if envoltura is None:
        return None
    return [a_diccionario(h)
            for h in envoltura.findall(f"{{{ESPACIO}}}{singular}")]


class ClienteXml:
    """Sesión con los microservicios, solo en XML."""

    def __init__(self, servicios=None, tiempo=None):
        self.servicios = dict(servicios or SERVICIOS)
        self.tiempo = tiempo or TIEMPO_LIMITE
        self.token = None
        self.token_refresco = None
        self.usuario = None
        self.nombre = None
        self.perfil = None
        self.unidad_alcance = None
        self.permisos = set()
        # Ultima respuesta en crudo, para la pestana de Diagnostico. Se
        # guarda el texto tal cual llego: reconstruirlo desde el arbol ya
        # parseado mostraria algo PARECIDO a lo que mando el servicio, y
        # cuando se depura un problema de contrato lo parecido no sirve.
        self.ultimo_xml = ""
        self.ultimo_servicio = ""

    # ------------------------------------------------------------ interno
    def _url(self, servicio, ruta):
        base = self.servicios.get(servicio)
        if not base:
            raise ErrorCliente("SERVICIO_NO_CONFIGURADO",
                               f"No hay direccion configurada para '{servicio}'.")
        return base.rstrip("/") + ruta

    def pedir(self, servicio, ruta, xsd, metodo="GET", cuerpo_xml=None,
              raiz_esperada=None, sin_token=False):
        """Hace la petición, valida la respuesta y devuelve el árbol.

        El orden importa: primero se valida contra el XSD y solo después se
        lee. Leer primero y validar después dejaría a la interfaz mostrando
        datos de un documento que no cumple el contrato.
        """
        cabeceras = {"Accept": "application/xml"}
        datos = None
        if cuerpo_xml is not None:
            datos = cuerpo_xml.encode("utf8")
            cabeceras["Content-Type"] = "application/xml; charset=utf-8"
        if self.token and not sin_token:
            cabeceras["Authorization"] = f"Bearer {self.token}"

        peticion = urllib.request.Request(
            self._url(servicio, ruta), data=datos, headers=cabeceras,
            method=metodo)
        try:
            with urllib.request.urlopen(peticion, timeout=self.tiempo) as r:
                crudo, codigo = r.read(), r.status
        except urllib.error.HTTPError as e:
            crudo, codigo = e.read(), e.code
        except urllib.error.URLError as e:
            raise ErrorCliente(
                "SIN_CONEXION",
                f"No se pudo contactar al servicio de {servicio}: "
                f"{getattr(e, 'reason', e)}. Revisa que los contenedores "
                f"esten arriba.")

        self.ultimo_servicio = servicio
        self.ultimo_xml = (f"<!-- {metodo} {self._url(servicio, ruta)} "
                           f"-> {codigo} -->\n"
                           + crudo.decode("utf8", "replace"))

        if not crudo:
            raise ErrorCliente("RESPUESTA_VACIA",
                               f"El servicio de {servicio} respondio {codigo} "
                               f"sin cuerpo.", codigo)
        try:
            doc = etree.fromstring(crudo)
        except etree.XMLSyntaxError as e:
            raise ErrorCliente(
                "XML_MAL_FORMADO",
                f"El servicio de {servicio} respondio algo que no es XML "
                f"bien formado: {e}", codigo)

        nombre_raiz = etree.QName(doc).localname

        # Un sobre de error se valida contra comun.xsd y se convierte en
        # ErrorCliente con su codigo estable.
        if nombre_raiz == "error_respuesta":
            self._validar(doc, "comun.xsd", servicio)
            error = doc.find(f"{{{ESPACIO}}}error")
            detalles_nodo = error.find(f"{{{ESPACIO}}}detalles")
            detalles = []
            if detalles_nodo is not None:
                for d in detalles_nodo.findall(f"{{{ESPACIO}}}detalle"):
                    detalles.append({"campo": _texto(d, "campo"),
                                     "problema": _texto(d, "problema")})
            raise ErrorCliente(_texto(error, "codigo") or "ERROR",
                               _texto(error, "mensaje") or "Error del servicio.",
                               codigo, detalles)

        if codigo >= 400:
            raise ErrorCliente("RESPUESTA_INESPERADA",
                               f"El servicio de {servicio} respondio {codigo} "
                               f"con un documento <{nombre_raiz}> en lugar de "
                               f"un sobre de error.", codigo)

        self._validar(doc, xsd, servicio)

        if raiz_esperada and nombre_raiz != raiz_esperada:
            raise ErrorCliente(
                "RAIZ_INESPERADA",
                f"Se esperaba <{raiz_esperada}> y llego <{nombre_raiz}>. El "
                f"servicio de {servicio} cambio su contrato.", codigo)
        return doc

    @staticmethod
    def _validar(doc, xsd, servicio):
        esq = esquema(xsd)
        if not esq.validate(doc):
            detalles = [{"campo": str(e.line), "problema": e.message}
                        for e in esq.error_log][:6]
            raise ErrorCliente(
                "CONTRATO_INCUMPLIDO",
                f"La respuesta del servicio de {servicio} no cumple {xsd}. La "
                f"aplicacion no la muestra: podria tener campos faltantes o un "
                f"nulo interpretado como cero.",
                detalles=detalles)

    # ------------------------------------------------------------- sesión
    def iniciar_sesion(self, correo, contrasena):
        """Inicio de sesión en XML. El token no se guarda en disco.

        Vive en memoria mientras la ventana está abierta. Guardarlo en un
        archivo lo dejaría legible para cualquier programa del equipo, y el
        token sirve para hablar con los nueve componentes.
        """
        cuerpo = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
                  f'<solicitud_login xmlns="{ESPACIO}">\n'
                  f'  <correo>{_escapar(correo)}</correo>\n'
                  f'  <contrasena>{_escapar(contrasena)}</contrasena>\n'
                  f'</solicitud_login>')
        doc = self.pedir("auth", "/api/v1/auth/login?formato=xml", "sesion.xsd",
                         "POST", cuerpo, sin_token=True)
        self.token = _texto(doc, "token_acceso")
        self.token_refresco = _texto(doc, "token_renovacion")
        # Los datos del usuario van ANIDADOS en <usuario>, no sueltos en la
        # raiz. Leerlos de la raiz devolvia None en los tres campos y la
        # ventana se abria sin saber quien habia entrado.
        usuario = doc.find(f"{{{ESPACIO}}}usuario")
        self.usuario = _texto(usuario, "usuario_id") if usuario is not None else None
        self.nombre = _texto(usuario, "nombre") if usuario is not None else None
        self.perfil = _texto(usuario, "perfil") if usuario is not None else None
        self.unidad_alcance = (_texto(usuario, "unidad_alcance")
                               if usuario is not None else None)
        if not self.token:
            raise ErrorCliente("SIN_TOKEN",
                               "El servicio no devolvio token de acceso.")
        # Los permisos NO vienen en la respuesta de login, y eso es correcto:
        # en este sistema los permisos se consultan por peticion contra
        # usuarios.perfil_permiso y nunca viajan dentro del token. Si
        # viajaran, revocar un permiso no tendria efecto hasta que el token
        # expirara. La aplicacion los pide aparte, y los usa solo para
        # decidir que pestanas muestra: la autorizacion de verdad la hace
        # cada servicio.
        self.permisos = set(self.permisos_vigentes())
        return {"usuario_id": self.usuario, "nombre": self.nombre,
                "perfil": self.perfil, "unidad_alcance": self.unidad_alcance,
                "permisos": sorted(self.permisos)}

    def permisos_vigentes(self):
        """Pide los permisos del perfil al servicio, en XML."""
        doc = self.pedir("auth", "/api/v1/auth/permisos?formato=xml",
                         "sesion.xsd", raiz_esperada="permisos_respuesta")
        return lista_de(doc, "permisos", "permiso") or []

    def validar_sesion(self):
        """Confirma contra el servicio que el token sigue vivo.

        No basta con que el JWT no haya expirado: la sesión puede haberse
        revocado desde el portal, y la lista de revocados vive en Redis. Un
        cliente que solo mirara la fecha del token seguiría trabajando con
        una sesión cerrada.
        """
        doc = self.pedir("auth", "/api/v1/auth/validar?formato=xml",
                         "sesion.xsd")
        return a_diccionario(doc)

    def renovar(self):
        if not self.token_refresco:
            raise ErrorCliente("SIN_REFRESCO",
                               "Esta sesion no trae token de refresco.")
        cuerpo = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
                  f'<solicitud_renovar xmlns="{ESPACIO}">\n'
                  f'  <token_renovacion>{_escapar(self.token_refresco)}'
                  f'</token_renovacion>\n'
                  f'</solicitud_renovar>')
        doc = self.pedir("auth", "/api/v1/auth/renovar?formato=xml",
                         "sesion.xsd", "POST", cuerpo, sin_token=True)
        self.token = _texto(doc, "token_acceso") or self.token
        nuevo_refresco = _texto(doc, "token_renovacion")
        if nuevo_refresco:
            # El refresco se rota: el anterior deja de servir. Si no se
            # guardara el nuevo, la siguiente renovacion fallaria.
            self.token_refresco = nuevo_refresco
        return self.token

    def cerrar_sesion(self):
        """Cierra sesión en el servidor y borra las credenciales locales."""
        try:
            if self.token:
                self.pedir("auth", "/api/v1/auth/logout?formato=xml",
                           "sesion.xsd", "POST")
        except ErrorCliente:
            # Aun si el servicio no responde, las credenciales locales se
            # borran: dejarlas en memoria tras un cierre de sesion seria
            # peor que no poder avisarle al servidor.
            pass
        finally:
            self.token = self.token_refresco = None
            self.usuario = self.nombre = self.perfil = None
            self.unidad_alcance = None
            self.permisos = set()

    def puede(self, *codigos):
        return bool(self.permisos & set(codigos))

    # ------------------------------------- proceso: solicitudes de apoyo
    def solicitudes_apoyo(self, estado=None, pagina=1, tamano=25):
        consulta = f"?formato=xml&pagina={pagina}&tamano={tamano}"
        if estado:
            consulta += f"&estado={urllib.parse.quote(estado)}"
        doc = self.pedir("proceso", f"/api/v1/solicitudes-apoyo{consulta}",
                         "proceso.xsd", raiz_esperada="solicitudes_apoyo")
        return (lista_de(doc, "solicitudes", "solicitud") or [],
                a_diccionario(doc.find(f"{{{ESPACIO}}}paginacion"))
                if doc.find(f"{{{ESPACIO}}}paginacion") is not None else None)

    def cambiar_estado_solicitud(self, solicitud_id, estado, nota=None):
        """Captura y modificación de datos, en XML."""
        partes = [f"  <estado>{_escapar(estado)}</estado>"]
        if nota:
            partes.append(f"  <nota>{_escapar(nota)}</nota>")
        cuerpo = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
                  f'<cambio_estado xmlns="{ESPACIO}">\n'
                  + "\n".join(partes) +
                  f'\n</cambio_estado>')
        doc = self.pedir("proceso",
                         f"/api/v1/solicitudes-apoyo/"
                         f"{urllib.parse.quote(solicitud_id)}/estado?formato=xml",
                         "proceso.xsd", "PATCH", cuerpo,
                         raiz_esperada="solicitud_apoyo")
        return a_diccionario(doc)

    # --------------------------------------------- consultas y tableros
    def tablero(self, unidad_id, campania_id=None):
        consulta = "?formato=xml"
        if campania_id:
            consulta += f"&campania_id={urllib.parse.quote(campania_id)}"
        doc = self.pedir("consultas",
                         f"/api/v1/consultas/tablero/unidad/"
                         f"{urllib.parse.quote(unidad_id)}{consulta}",
                         "consultas.xsd", raiz_esperada="tablero_respuesta")
        return lista_de(doc, "filas", "fila") or []

    def participacion(self):
        doc = self.pedir("consultas", "/api/v1/consultas/participacion?formato=xml",
                         "consultas.xsd", raiz_esperada="participacion_respuesta")
        return lista_de(doc, "elementos", "elemento") or []

    # ------------------------------------------------------- catálogos
    def unidades(self, pagina=1, tamano=100):
        doc = self.pedir("catalogos",
                         f"/api/v1/catalogos/unidades"
                         f"?formato=xml&pagina={pagina}&tamano={tamano}",
                         "catalogos.xsd", raiz_esperada="unidades_respuesta")
        return lista_de(doc, "unidades", "unidad") or []

    # ------------------------------------------------------ algoritmos
    def detecciones(self, campania_id=None, nivel=None, pagina=1, tamano=50):
        consulta = f"?formato=xml&pagina={pagina}&tamano={tamano}"
        if campania_id:
            consulta += f"&campania_id={urllib.parse.quote(campania_id)}"
        if nivel:
            consulta += f"&nivel={urllib.parse.quote(nivel)}"
        doc = self.pedir("algoritmos", f"/api/v1/algoritmos/detecciones{consulta}",
                         "algoritmos.xsd", raiz_esperada="detecciones_respuesta")
        return lista_de(doc, "detecciones", "deteccion") or []

    def reglas(self):
        doc = self.pedir("algoritmos", "/api/v1/algoritmos/reglas?formato=xml",
                         "algoritmos.xsd", raiz_esperada="reglas_respuesta")
        return lista_de(doc, "reglas", "regla") or []

    # --------------------------------------------------------- reportes
    def catalogo_reportes(self):
        doc = self.pedir("reportes", "/api/v1/reportes/catalogo?formato=xml",
                         "reportes.xsd", raiz_esperada="catalogo_reportes_respuesta")
        return lista_de(doc, "elementos", "elemento") or []

    def generar_reporte(self, tipo, parametro=None):
        partes = [f"  <tipo>{_escapar(tipo)}</tipo>"]
        if parametro:
            partes.append(f"  <parametro>{_escapar(parametro)}</parametro>")
        cuerpo = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
                  f'<solicitud_reporte xmlns="{ESPACIO}">\n'
                  + "\n".join(partes) + f'\n</solicitud_reporte>')
        doc = self.pedir("reportes", "/api/v1/reportes?formato=xml",
                         "reportes.xsd", "POST", cuerpo,
                         raiz_esperada="reporte_respuesta")
        return a_diccionario(doc)

    def descargar_reporte(self, reporte_id):
        """Trae el contenido del reporte en XML, validado contra reportes.xsd."""
        doc = self.pedir("reportes",
                         f"/api/v1/reportes/{urllib.parse.quote(reporte_id)}"
                         f"/contenido?formato=xml",
                         "reportes.xsd", raiz_esperada="reporte")
        return a_diccionario(doc)


def _escapar(texto):
    """Escapa para contenido de elemento XML.

    Se escapan los cinco caracteres, incluidas las comillas: el mismo
    ayudante se usa para atributos en versiones futuras, y un escape
    incompleto ahí es una inyección.
    """
    return (str(texto).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;"))


def exportar_csv(filas, columnas, ruta):
    """Exportación inicial. QUOTE_ALL por el mismo motivo que en el servicio.

    La explicación de una regla de riesgo trae comas; una sola coma sin
    comillas corre todas las columnas siguientes y el archivo deja de ser
    legible sin que nada falle.
    """
    import csv
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.writer(f, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
        escritor.writerow(columnas)
        for fila in filas:
            escritor.writerow(["" if fila.get(c) is None else fila.get(c)
                               for c in columnas])
    return ruta
