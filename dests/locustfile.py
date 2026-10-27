"""Prueba de estrés del catálogo que responde en http://127.0.0.1:5001.

Locust crea una instancia de ``UsuarioCatalogo`` por cada usuario virtual.
Al ejecutar este archivo son 20 instancias al mismo tiempo. Cada una elige
una tarea según su peso, hace la petición y espera ``wait_time`` antes de
la siguiente. Locust anota lo que ve el cliente (tiempos, fallos, RPS).
No mide CPU ni RAM del proceso del catálogo.

Uso:
    python locustfile.py

La interfaz web queda en http://127.0.0.1:8089.
"""

import uuid
from pathlib import Path

from locust import HttpUser, between, task

# 20 usuarios vivos a la vez. El spawn rate es cuántos entran por segundo.
USUARIOS = 20
SPAWN_RATE = 5
HOST = "http://127.0.0.1:5001"
WEB_HOST = "127.0.0.1"
WEB_PORT = 8089

# 1984 está en el catálogo de demostración. El otro ISBN no existe.
ISBN = "9780451524935"
ISBN_AUSENTE = "0000000000000"
# Concepto SOAP de demostración (Máquinas virtuales / IaaS).
CONCEPTO_ID = "101"
ISBN_CONCEPTO = "9780134444245"

TNS = "http://udem.edu.mx/iac/library-classifier"
SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"
WSSE = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"

# Credencial de demostración del propio servicio. Solo abre
# ObtenerEstadisticasPorModelo cuando el proceso está en modo demo.
SOAP_USUARIO = "soap_stats"
SOAP_PASSWORD = "laboratorio"


def sobre_soap(cuerpo, con_credencial=False):
    """Arma un Envelope SOAP 1.1.

    ``cuerpo`` es el XML de la operación, ya con el prefijo ``tns``.
    Si ``con_credencial`` es verdadero, el Header lleva el UsernameToken
    de las estadísticas.
    """
    cabecera = ""
    if con_credencial:
        cabecera = f"""
  <soap:Header>
    <wsse:Security xmlns:wsse="{WSSE}">
      <wsse:UsernameToken>
        <wsse:Username>{SOAP_USUARIO}</wsse:Username>
        <wsse:Password>{SOAP_PASSWORD}</wsse:Password>
      </wsse:UsernameToken>
    </wsse:Security>
  </soap:Header>"""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="{SOAP_ENV}" xmlns:tns="{TNS}">{cabecera}
  <soap:Body>
    {cuerpo}
  </soap:Body>
</soap:Envelope>
"""


class UsuarioCatalogo(HttpUser):
    """Cliente virtual del catálogo.

    Una instancia es un usuario. Con 20 usuarios hay 20 clientes HTTP
    independientes. ``host`` es el microservicio. ``wait_time`` es la
    pausa, en segundos, entre una tarea y la siguiente.

    Rutas que cubre esta clase:

    - GET / , /probar.html , /site-style.css , /site-js.js
    - GET /css/probar.css , /js/soap-modulo.js
    - GET /covers/<archivo>
    - GET /books , /books/<isbn> , /cloud-concepts , /books-images
    - GET /soap , /wsdl
    - POST /soap , POST /demo/reset
    - POST /books , PUT /books/<isbn> , DELETE /books/<isbn>
    """

    host = HOST
    wait_time = between(1, 2)

    def on_start(self):
        """Corre una sola vez, cuando Locust crea al usuario.

        Ejercita ``RegistrarClasificacion`` con un correo nuevo. Así la
        operación de alta se prueba sin repetirla en cada ciclo (un
        segundo envío del mismo concepto responde 409, duplicado).
        """
        correo = f"locust-{uuid.uuid4().hex[:12]}@udem.edu"
        cuerpo = f"""
    <tns:RegistrarClasificacion>
      <tns:nombre>Locust</tns:nombre>
      <tns:apellidos>Estres</tns:apellidos>
      <tns:correo>{correo}</tns:correo>
      <tns:conceptId>{CONCEPTO_ID}</tns:conceptId>
      <tns:isbn>{ISBN_CONCEPTO}</tns:isbn>
      <tns:modelo>IaaS</tns:modelo>
      <tns:tipoCliente>locust</tns:tipoCliente>
    </tns:RegistrarClasificacion>"""
        self._post_soap(
            cuerpo,
            "POST /soap RegistrarClasificacion",
            (200,),
            "RegistrarClasificacionResponse",
        )

    def _marcar(self, response, codigos, tipo=None, texto=None):
        """Cierra una petición abierta con ``catch_response``.

        ``codigos`` son los HTTP que el contrato de esa ruta acepta.
        ``tipo`` es un fragmento del Content-Type. ``texto`` tiene que
        aparecer en el cuerpo. Si algo no cuadra, la fila sale en rojo
        en la interfaz.
        """
        if response.status_code not in codigos:
            esperados = ", ".join(str(codigo) for codigo in sorted(codigos))
            response.failure(f"HTTP {response.status_code}; se esperaba {esperados}")
            return
        content_type = response.headers.get("Content-Type") or ""
        if tipo is not None and tipo not in content_type:
            response.failure(f"Content-Type inesperado: {content_type}")
            return
        if texto is not None and texto not in response.text:
            response.failure(f"el cuerpo no contiene {texto!r}")
            return
        response.success()

    def _get(self, ruta, nombre, codigos=(200,), tipo=None, texto=None):
        """GET. ``nombre`` es el texto de la fila en las estadísticas."""
        with self.client.get(ruta, name=nombre, catch_response=True) as response:
            self._marcar(response, codigos, tipo, texto)

    def _escribir_sin_admin(self, metodo, ruta, nombre, cuerpo=None):
        """POST, PUT o DELETE de /books sin el rol admin.

        El servicio solo modifica el catálogo si llega la cabecera
        ``X-User-Role: admin`` (o ``?role=admin``). Sin ese dato responde
        403 y no toca el libro. Ese 403 es el resultado correcto aquí:
        la prueba de estrés no borra ni crea títulos.
        """
        kwargs = {"name": nombre, "catch_response": True}
        if cuerpo is not None:
            kwargs["json"] = cuerpo
        with metodo(ruta, **kwargs) as response:
            self._marcar(response, (403,), texto="Se requiere usuario admin")

    def _post_soap(self, cuerpo, nombre, codigos, texto, con_credencial=False):
        """POST /soap con un Envelope. El cuerpo vacío no pasa por aquí."""
        xml = sobre_soap(cuerpo, con_credencial=con_credencial)
        with self.client.post(
            "/soap",
            data=xml.encode("utf-8"),
            headers={"Content-Type": "text/xml; charset=utf-8"},
            name=nombre,
            catch_response=True,
        ) as response:
            self._marcar(response, codigos, tipo="xml", texto=texto)

    # --- Catálogo /books (las tres URLs del ejercicio) ---

    @task(6)
    def listar_libros_xml(self):
        """GET /books. Sin ``format`` el catálogo sale en XML."""
        self._get("/books", "GET /books XML", tipo="xml", texto=ISBN)

    @task(6)
    def listar_libros_json(self):
        """GET /books?format=json. El mismo catálogo, en JSON."""
        self._get("/books?format=json", "GET /books JSON", tipo="json", texto=ISBN)

    @task(6)
    def listar_libros_format_xml(self):
        """GET /books?format=xml. Pide XML de forma explícita."""
        self._get("/books?format=xml", "GET /books format=xml", tipo="xml", texto=ISBN)

    @task(1)
    def listar_libros_alias_json(self):
        """GET /books?format-json. Alias que también pide JSON."""
        self._get("/books?format-json", "GET /books format-json", tipo="json", texto=ISBN)

    @task(3)
    def obtener_libro_xml(self):
        """GET /books/{isbn}. Ficha de 1984 en XML."""
        self._get(f"/books/{ISBN}", "GET /books/{isbn} XML", tipo="xml", texto="1984")

    @task(3)
    def obtener_libro_json(self):
        """GET /books/{isbn}?format=json. La misma ficha en JSON."""
        self._get(
            f"/books/{ISBN}?format=json",
            "GET /books/{isbn} JSON",
            tipo="json",
            texto="1984",
        )

    @task(2)
    def obtener_libro_format_xml(self):
        """GET /books/{isbn}?format=xml. La ficha con XML explícito."""
        self._get(
            f"/books/{ISBN}?format=xml",
            "GET /books/{isbn} format=xml",
            tipo="xml",
            texto="1984",
        )

    @task(1)
    def libro_inexistente(self):
        """GET /books/{isbn} con un ISBN que no está. El contrato es 404."""
        self._get(
            f"/books/{ISBN_AUSENTE}",
            "GET /books/{isbn} ausente",
            codigos=(404,),
            texto="Libro no encontrado",
        )

    # --- Otras lecturas del catálogo ---

    @task(2)
    def conceptos_nube_xml(self):
        """GET /cloud-concepts. IaaS, PaaS, SaaS y FaaS en XML."""
        self._get("/cloud-concepts", "GET /cloud-concepts XML", tipo="xml", texto="IaaS")

    @task(2)
    def conceptos_nube_json(self):
        """GET /cloud-concepts?format=json. Los mismos modelos en JSON."""
        self._get(
            "/cloud-concepts?format=json",
            "GET /cloud-concepts JSON",
            tipo="json",
            texto="FaaS",
        )

    @task(1)
    def conceptos_nube_format_xml(self):
        """GET /cloud-concepts?format=xml. XML pedido de forma explícita."""
        self._get(
            "/cloud-concepts?format=xml",
            "GET /cloud-concepts format=xml",
            tipo="xml",
            texto="IaaS",
        )

    @task(2)
    def imagenes_xml(self):
        """GET /books-images. Datos mínimos y portadas, en XML."""
        self._get("/books-images", "GET /books-images XML", tipo="xml", texto=ISBN)

    @task(2)
    def imagenes_json(self):
        """GET /books-images?format=json. La misma lista en JSON."""
        self._get(
            "/books-images?format=json",
            "GET /books-images JSON",
            tipo="json",
            texto=ISBN,
        )

    @task(1)
    def imagenes_format_xml(self):
        """GET /books-images?format=xml. XML pedido de forma explícita."""
        self._get(
            "/books-images?format=xml",
            "GET /books-images format=xml",
            tipo="xml",
            texto=ISBN,
        )

    @task(2)
    def portada(self):
        """GET /covers/{isbn}.svg. SVG de la portada."""
        self._get(f"/covers/{ISBN}.svg", "GET /covers/{isbn}.svg", tipo="svg", texto="<svg")

    @task(1)
    def portada_por_nombre(self):
        """GET /covers/cover-{isbn}.png. El servicio localiza el SVG por el ISBN del nombre."""
        self._get(
            f"/covers/cover-{ISBN}.png",
            "GET /covers/cover-{isbn}.png",
            tipo="svg",
            texto="<svg",
        )

    # --- Páginas y estáticos ---

    @task(1)
    def indice_html(self):
        """GET /. Página HTML para probar el módulo SOAP."""
        self._get("/", "GET / HTML", tipo="html", texto="SOAP")

    @task(1)
    def indice_json(self):
        """GET /?format=json. Descriptor del servicio y de sus rutas."""
        self._get("/?format=json", "GET / JSON", tipo="json", texto="LibraryClassifier")

    @task(1)
    def indice_xml(self):
        """GET /?format=xml. El mismo descriptor en XML."""
        self._get("/?format=xml", "GET / XML", tipo="xml", texto="LibraryClassifier")

    @task(1)
    def pagina_probar(self):
        """GET /probar.html. La página de prueba, por su ruta directa."""
        self._get("/probar.html", "GET /probar.html", tipo="html", texto="SOAP")

    @task(1)
    def estilo_sitio(self):
        """GET /site-style.css. Hoja de estilo del sitio."""
        self._get("/site-style.css", "GET /site-style.css", tipo="css")

    @task(1)
    def script_sitio(self):
        """GET /site-js.js. Script del sitio."""
        self._get("/site-js.js", "GET /site-js.js", tipo="javascript", texto="menu-btn")

    @task(1)
    def estilo_prueba(self):
        """GET /css/probar.css. Hoja de la pantalla de prueba SOAP."""
        self._get("/css/probar.css", "GET /css/probar.css", tipo="css", texto="soap-layout")

    @task(1)
    def script_soap(self):
        """GET /js/soap-modulo.js. Arma los Envelope desde el navegador."""
        self._get("/js/soap-modulo.js", "GET /js/soap-modulo.js", tipo="javascript", texto=TNS)

    # --- WSDL y SOAP ---

    @task(2)
    def wsdl(self):
        """GET /soap. Sin cuerpo, esta ruta entrega el WSDL."""
        self._get("/soap", "GET /soap WSDL", tipo="xml", texto="definitions")

    @task(1)
    def wsdl_alias(self):
        """GET /wsdl. Alias de GET /soap."""
        self._get("/wsdl", "GET /wsdl", tipo="xml", texto="definitions")

    @task(1)
    def soap_info_json(self):
        """GET /soap?format=json. Lista las cuatro operaciones SOAP."""
        self._get(
            "/soap?format=json",
            "GET /soap JSON",
            tipo="json",
            texto="ObtenerConceptosPendientes",
        )

    @task(2)
    def soap_conceptos_pendientes(self):
        """POST /soap ObtenerConceptosPendientes. Lectura del catálogo SOAP."""
        cuerpo = """
    <tns:ObtenerConceptosPendientes>
      <tns:correo>estudiante@udem.edu</tns:correo>
      <tns:tipoCliente>locust</tns:tipoCliente>
    </tns:ObtenerConceptosPendientes>"""
        self._post_soap(
            cuerpo,
            "POST /soap ObtenerConceptosPendientes",
            (200,),
            "ObtenerConceptosPendientesResponse",
        )

    @task(2)
    def soap_progreso(self):
        """POST /soap ObtenerProgresoUsuario. Progreso de un correo."""
        cuerpo = """
    <tns:ObtenerProgresoUsuario>
      <tns:correo>estudiante@udem.edu</tns:correo>
    </tns:ObtenerProgresoUsuario>"""
        self._post_soap(
            cuerpo,
            "POST /soap ObtenerProgresoUsuario",
            (200,),
            "ObtenerProgresoUsuarioResponse",
        )

    @task(1)
    def soap_estadisticas(self):
        """POST /soap ObtenerEstadisticasPorModelo con el UsernameToken de demo."""
        self._post_soap(
            "<tns:ObtenerEstadisticasPorModelo/>",
            "POST /soap ObtenerEstadisticasPorModelo",
            (200,),
            "ObtenerEstadisticasPorModeloResponse",
            con_credencial=True,
        )

    @task(1)
    def soap_estadisticas_sin_credencial(self):
        """POST /soap ObtenerEstadisticasPorModelo sin WS-Security. Contrato: 401."""
        self._post_soap(
            "<tns:ObtenerEstadisticasPorModelo/>",
            "POST /soap estadisticas sin credencial",
            (401,),
            "Fault",
        )

    @task(1)
    def soap_cuerpo_vacio(self):
        """POST /soap sin cuerpo. Fault de cliente, HTTP 400."""
        with self.client.post(
            "/soap",
            data=b"",
            headers={"Content-Type": "text/xml; charset=utf-8"},
            name="POST /soap cuerpo vacio",
            catch_response=True,
        ) as response:
            self._marcar(response, (400,), tipo="xml", texto="Fault")

    # --- Escrituras. Sin rol admin, a propósito. ---

    @task(1)
    def crear_libro_sin_admin(self):
        """POST /books sin rol admin. Debe responder 403 y no crear el libro."""
        self._escribir_sin_admin(
            self.client.post,
            "/books?format=json",
            "POST /books sin admin",
            {"isbn": "9999999999999", "title": "No debe crearse"},
        )

    @task(1)
    def reemplazar_libro_sin_admin(self):
        """PUT /books/{isbn} sin rol admin. Debe responder 403."""
        self._escribir_sin_admin(
            self.client.put,
            f"/books/{ISBN}?format=json",
            "PUT /books/{isbn} sin admin",
            {"title": "No debe cambiar", "authors": ["Nadie"], "category": "Novela"},
        )

    @task(1)
    def borrar_libro_sin_admin(self):
        """DELETE /books/{isbn} sin rol admin. Debe responder 403 y el libro sigue."""
        self._escribir_sin_admin(
            self.client.delete,
            f"/books/{ISBN}?format=json",
            "DELETE /books/{isbn} sin admin",
        )

    @task(1)
    def reiniciar_demo(self):
        """POST /demo/reset. En modo demostración restaura el estado en memoria (200).

        Si el modo demo está apagado, la misma ruta responde 404.
        """
        with self.client.post("/demo/reset", name="POST /demo/reset", catch_response=True) as response:
            self._marcar(response, (200, 404))


def abrir_interfaz():
    """Abre Locust en http://127.0.0.1:8089 y arranca los 20 usuarios.

    ``--autostart`` dispara el enjambre al abrir el proceso. La interfaz
    sigue disponible para ver RPS, percentiles y fallos, y para detener
    o cambiar el número de usuarios.
    """
    import sys

    from locust.main import main

    sys.argv = [
        "locust",
        "-f",
        str(Path(__file__).resolve()),
        "--host",
        HOST,
        "--web-host",
        WEB_HOST,
        "--web-port",
        str(WEB_PORT),
        "--users",
        str(USUARIOS),
        "--spawn-rate",
        str(SPAWN_RATE),
        "--autostart",
    ]
    main()


if __name__ == "__main__":
    abrir_interfaz()
