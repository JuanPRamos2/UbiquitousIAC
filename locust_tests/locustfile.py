"""Comparación de rendimiento: monolito Node y seis microservicios Flask.

Qué mide Locust
    El tiempo que ve el cliente: desde que envía la petición hasta que
    recibe la respuesta completa. Con eso calcula solicitudes por segundo
    (RPS), percentiles (p50, p95, …) y el porcentaje de fallos.
    No mide CPU, RAM ni disco del servidor. Un p95 alto puede venir del
    proceso, de PostgreSQL, de Redis o de la red entre esta máquina y GCP.

Piezas de este archivo
    HttpUser
        Un usuario virtual. Locust crea una instancia por usuario concurrente.
        Cada instancia tiene su propia cookie jar.
    @task
        Una acción que el usuario repite. El número es el peso: con peso 1
        todas las tareas de este archivo se eligen con la misma frecuencia.
    wait_time = between(1, 2)
        Pausa aleatoria de 1 a 2 segundos después de cada tarea. No es tiempo
        de respuesta. Baja el RPS a propósito para parecerse a una persona
        y no a un bombardeo sin espera. Con N usuarios, el RPS queda cerca de
        N / (tiempo_de_respuesta + espera), no de la capacidad máxima.
    usuarios
        Cuántas instancias viven a la vez. Lo fija la clase PerfilCarga.
    spawn_rate
        Cuántos de esos usuarios entran por segundo durante la rampa.
    duración
        Segundos hasta que tick() devuelve None y Locust se detiene.

Umbral de esta práctica
    El servicio se considera degradado si el p95 de una solicitud supera
    1000 ms o si sus fallos superan el 5 %. Hace falta un mínimo de 30
    respuestas de esa solicitud antes de juzgarla, para no parar la rampa
    por un único fallo de arranque. Es un límite didáctico del equipo local,
    no la capacidad máxima del sistema.

Perfiles (LOCUST_PROFILE)
    smoke        1 usuario, 30 s. Comprueba que el escenario responde.
    load         5 usuarios, spawn 1/s, 2 min. Carga estable esperada.
    stress       De 2 a 20 usuarios, de 2 en 2, cada etapa 18 s, 3 min.
    spike        2 usuarios, salto a 15, breve meseta y vuelta a 2. 2 min.
    soak         3 usuarios durante 4 min. Miniatura; un soak real dura horas.
    breakpoint   De 1 hacia 20, +1 cada 12 s, tope 4 min. Al incumplir el
                 umbral deja de subir y mantiene ese número de usuarios.

Puertos
    El enunciado lista pagos en 5002, pedidos en 5003, users en 5004 y
    autores en 5005. Este repositorio no está cableado así. run-all.sh y
    config.py publican:

        3000  monolito
        5000  login
        5001  books
        5002  users
        5003  autores
        5004  pedidos
        5005  pagos

    Las pruebas usan esos puertos. Medir el puerto del enunciado atribuiría
    la latencia de un servicio a otro.

Rutas
    Solo lecturas. La salud confirma que el proceso responde, no que el
    catálogo o los pedidos funcionen. Por eso cada servicio tiene además
    una lectura de negocio cuando es pública.
    users, pedidos y pagos exigen JWT. El monolito exige sesión para
    /library/books. Esas rutas solo entran si existen las variables de
    entorno LOCUST_EMAIL y LOCUST_PASSWORD. No hay contraseñas ni tokens
    en este archivo.
    GET /login del microservicio de login no se llama: sin cuerpo, el
    código rellena el usuario administrador de demostración y abre sesión.

Uso en la instancia GCP (no en localhost):

    export LOCUST_TARGET_IP=<ip_publica>
    export LOCUST_PROFILE=smoke
    locust -f locust_tests/locustfile.py --headless --csv evidencias/smoke --html evidencias/smoke.html
"""

from __future__ import annotations

import os

from locust import HttpUser, LoadTestShape, between, task

P95_MS = 1000
ERROR_MAX = 0.05
MUESTRAS_MINIMAS = 30
ESPERA = between(1, 2)
ISBN = "9780451524935"


def _ip_objetivo() -> str:
    ip = os.environ.get("LOCUST_TARGET_IP", "").strip()
    if not ip:
        raise SystemExit(
            "Define LOCUST_TARGET_IP con la IP pública de la instancia GCP. "
            "Locust no debe apuntar a localhost."
        )
    prohibidas = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
    if ip.lower() in prohibidas or ip.startswith("127.") or ip.startswith("["):
        raise SystemExit(
            f"LOCUST_TARGET_IP={ip!r} es una dirección local. "
            "Usa la IP externa de la instancia."
        )
    return ip


IP = _ip_objetivo()
MONOLITO = f"http://{IP}:3000"
LOGIN = f"http://{IP}:5000"
BOOKS = f"http://{IP}:5001"
USERS = f"http://{IP}:5002"
AUTORES = f"http://{IP}:5003"
PEDIDOS = f"http://{IP}:5004"
PAGOS = f"http://{IP}:5005"

EMAIL = os.environ.get("LOCUST_EMAIL", "").strip()
PASSWORD = os.environ.get("LOCUST_PASSWORD", "").strip()
CON_CREDENCIALES = bool(EMAIL and PASSWORD)


class ClienteComparacion(HttpUser):
    """Un solo tipo de usuario recorre todos los destinos.

    Con un usuario (smoke) las tareas se turnan, así que los siete
    procesos reciben tráfico. Si hubiera una clase por servicio, ese
    único usuario solo ejercería una de ellas.
    """

    host = MONOLITO
    wait_time = ESPERA

    def on_start(self):
        self.token = None
        self.catalogo_monolito = False
        if "127.0.0.1" in (self.host or "") or "localhost" in (self.host or ""):
            raise RuntimeError("El host de Locust no puede ser localhost.")
        if CON_CREDENCIALES:
            self._abrir_monolito()
            self._abrir_jwt()

    def _marcar(self, response, codigos: tuple[int, ...]) -> None:
        if response.status_code not in codigos:
            esperados = ", ".join(str(codigo) for codigo in codigos)
            response.failure(f"HTTP {response.status_code}; se esperaba {esperados}")
            return
        response.success()

    def _get(self, url: str, nombre: str, codigos: tuple[int, ...] = (200,)) -> None:
        with self.client.get(
            url,
            name=nombre,
            catch_response=True,
            allow_redirects=False,
            timeout=(5, 30),
        ) as response:
            self._marcar(response, codigos)

    def _abrir_monolito(self) -> None:
        with self.client.post(
            f"{MONOLITO}/library/login",
            data={"email": EMAIL, "password": PASSWORD},
            name="monolito POST /library/login (arranque)",
            catch_response=True,
            allow_redirects=False,
            timeout=(5, 30),
        ) as response:
            if response.status_code == 302:
                response.success()
                self.catalogo_monolito = True
            else:
                response.failure(
                    f"HTTP {response.status_code}; el catálogo del monolito exige sesión"
                )

    def _abrir_jwt(self) -> None:
        with self.client.post(
            f"{LOGIN}/login?format=json",
            json={"email": EMAIL, "password": PASSWORD},
            name="login POST /login?format=json (arranque)",
            catch_response=True,
            allow_redirects=False,
            timeout=(5, 30),
        ) as response:
            token = ""
            if response.status_code == 200:
                try:
                    token = str(response.json().get("token") or "")
                except ValueError:
                    token = ""
            if token:
                response.success()
                self.token = token
            else:
                response.failure(
                    f"HTTP {response.status_code}; sin token no se leen users, pedidos ni pagos"
                )

    @task(1)
    def monolito_raiz(self):
        # Disponibilidad. 302 hacia /library. No lee el catálogo.
        self._get(f"{MONOLITO}/", "monolito GET /", (302,))

    @task(1)
    def monolito_salud(self):
        # Texto OK. No consulta el tablero ni los libros.
        self._get(f"{MONOLITO}/library/health", "monolito GET /library/health")

    @task(1)
    def monolito_lectura(self):
        if self.catalogo_monolito:
            self._get(f"{MONOLITO}/library/books", "monolito GET /library/books")
            return
        # Página pública. No es el catálogo; es la lectura comparable sin sesión.
        self._get(f"{MONOLITO}/library/login", "monolito GET /library/login")

    @task(1)
    def login_salud(self):
        self._get(f"{LOGIN}/health?format=json", "login GET /health?format=json")

    @task(1)
    def login_sesion(self):
        # Lectura de negocio sin crear usuarios. Sin cookie responde sesión anónima.
        self._get(f"{LOGIN}/session?format=json", "login GET /session?format=json")

    @task(1)
    def books_salud(self):
        self._get(f"{BOOKS}/health?format=json", "books GET /health?format=json")

    @task(1)
    def books_catalogo(self):
        self._get(f"{BOOKS}/books?format=json", "books GET /books?format=json")

    @task(1)
    def books_uno(self):
        self._get(
            f"{BOOKS}/books/{ISBN}?format=json",
            "books GET /books/{isbn}?format=json",
        )

    @task(1)
    def autores_salud(self):
        self._get(f"{AUTORES}/health?format=json", "autores GET /health?format=json")

    @task(1)
    def autores_lista(self):
        self._get(f"{AUTORES}/authors", "autores GET /authors")

    @task(1)
    def users_salud(self):
        self._get(f"{USERS}/health?format=json", "users GET /health?format=json")

    @task(1)
    def pedidos_salud(self):
        self._get(f"{PEDIDOS}/health?format=json", "pedidos GET /health?format=json")

    @task(1)
    def pagos_salud(self):
        self._get(f"{PAGOS}/health?format=json", "pagos GET /health?format=json")

    if CON_CREDENCIALES:

        @task(1)
        def users_lista(self):
            if not self.token:
                return
            with self.client.get(
                f"{USERS}/users",
                name="users GET /users",
                headers={"Authorization": f"Bearer {self.token}"},
                catch_response=True,
                allow_redirects=False,
                timeout=(5, 30),
            ) as response:
                self._marcar(response, (200,))

        @task(1)
        def pedidos_lista(self):
            if not self.token:
                return
            with self.client.get(
                f"{PEDIDOS}/pedidos",
                name="pedidos GET /pedidos",
                headers={"Authorization": f"Bearer {self.token}"},
                catch_response=True,
                allow_redirects=False,
                timeout=(5, 30),
            ) as response:
                self._marcar(response, (200,))

        @task(1)
        def pagos_lista(self):
            if not self.token:
                return
            with self.client.get(
                f"{PAGOS}/pagos",
                name="pagos GET /pagos",
                headers={"Authorization": f"Bearer {self.token}"},
                catch_response=True,
                allow_redirects=False,
                timeout=(5, 30),
            ) as response:
                self._marcar(response, (200,))


class PerfilCarga(LoadTestShape):
    """Traduce LOCUST_PROFILE a usuarios y spawn_rate a lo largo del tiempo."""

    def tick(self):
        perfil = os.environ.get("LOCUST_PROFILE", "smoke").strip().lower()
        segundo = self.get_run_time()
        if perfil == "smoke":
            return (1, 1) if segundo < 30 else None
        if perfil == "load":
            return (5, 1) if segundo < 120 else None
        if perfil == "stress":
            if segundo >= 180:
                return None
            etapa = min(9, int(segundo // 18))
            return (2 + etapa * 2, 2)
        if perfil == "spike":
            if segundo >= 120:
                return None
            if segundo < 15:
                return (2, 2)
            if segundo < 55:
                return (15, 15)
            return (2, 10)
        if perfil == "soak":
            return (3, 1) if segundo < 240 else None
        if perfil == "breakpoint":
            return self._quiebre(segundo)
        raise SystemExit(
            "LOCUST_PROFILE debe ser smoke, load, stress, spike, soak o breakpoint."
        )

    def _quiebre(self, segundo: float):
        if segundo >= 240:
            return None
        tope = getattr(self, "_tope", None)
        if tope is None and self._incumple():
            vivos = 1
            if self.runner is not None:
                vivos = max(1, self.runner.user_count)
            self._tope = vivos
            tope = vivos
        if tope is not None:
            return (tope, 1)
        nivel = min(20, 1 + int(segundo // 12))
        return (nivel, 1)

    def _incumple(self) -> bool:
        if self.runner is None:
            return False
        for entrada in self.runner.stats.entries.values():
            if entrada.num_requests < MUESTRAS_MINIMAS:
                continue
            p95 = entrada.get_response_time_percentile(0.95) or 0
            if p95 > P95_MS or entrada.fail_ratio > ERROR_MAX:
                return True
        return False
