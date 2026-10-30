# Prueba de estrés del catálogo (`:5001`) con Locust

Locust simula usuarios contra el microservicio que ya responde en `http://127.0.0.1:5001`. Cada usuario es una instancia de `UsuarioCatalogo` en `locustfile.py`. Esta prueba levanta **20 usuarios al mismo tiempo** y recorre todas las rutas de ese servicio.

Locust mide lo que ve el cliente: peticiones por segundo (RPS), tiempos, percentiles y fallos. No mide CPU, RAM ni disco del servidor.

El archivo no arranca el microservicio y no modifica ese proyecto. El catálogo tiene que estar escuchando en el puerto 5001 antes de abrir Locust.

## Qué hay en esta carpeta

| Archivo | Para qué |
| --- | --- |
| `locustfile.py` | Usuarios, tareas y arranque de la interfaz en el puerto 8089 |
| `PROMPT.md` | Enunciado de la sesión |
| `requirements.txt` | Dependencia: Locust |
| `README.md` | Estas instrucciones |

## Comprobar el servicio

```bash
curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:5001/books?format=json"
curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:5001/books"
curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:5001/books?format=xml"
```

Los tres deben responder `200`.

Instala Locust una vez, desde esta carpeta, con el entorno del proyecto:

```bash
.venv/bin/pip install -r dests/requirements.txt
```

## Ver la prueba en el puerto 8089

Desde la raíz del repositorio:

```bash
.venv/bin/python dests/locustfile.py
```

Eso abre la interfaz en [http://127.0.0.1:8089](http://127.0.0.1:8089) y arranca el enjambre:

- **Users:** 20 (usuarios simultáneos)
- **Spawn rate:** 5 (entran 5 usuarios por segundo hasta llegar a 20)
- **Host:** `http://127.0.0.1:5001`

En la interfaz se ven, en vivo:

- **RPS:** peticiones por segundo que el servicio está contestando
- **Failures:** peticiones que no cumplieron el contrato de su ruta
- **Percentiles** (p50, p95, p99). El p95 es el tiempo por debajo del cual cae el 95 % de las respuestas
- Gráficas de usuarios, tiempo de respuesta y peticiones

**Stop** detiene el enjambre. `Ctrl+C` en la terminal cierra Locust. Puedes cambiar el número de usuarios en el formulario y pulsar **Start** otra vez.

El mismo arranque, escrito como comando de Locust:

```bash
.venv/bin/locust -f dests/locustfile.py --host http://127.0.0.1:5001 --web-host 127.0.0.1 --web-port 8089 --users 20 --spawn-rate 5 --autostart
```

## Corrida sin interfaz

Tabla en la terminal, 60 segundos, sin puerto 8089:

```bash
.venv/bin/locust -f dests/locustfile.py --host http://127.0.0.1:5001 --headless --users 20 --spawn-rate 5 --run-time 60s
```

## Endpoints

El peso es cuántas veces Locust prefiere esa tarea frente a una de peso 1. Después de cada tarea el usuario espera entre 1 y 2 segundos (`wait_time`).

### Catálogo

| Tarea | Petición | Resultado válido | Peso |
| --- | --- | --- | --- |
| `listar_libros_xml` | `GET /books` | 200 XML | 6 |
| `listar_libros_json` | `GET /books?format=json` | 200 JSON | 6 |
| `listar_libros_format_xml` | `GET /books?format=xml` | 200 XML | 6 |
| `listar_libros_alias_json` | `GET /books?format-json` | 200 JSON | 1 |
| `obtener_libro_xml` | `GET /books/9780451524935` | 200 XML, título 1984 | 3 |
| `obtener_libro_json` | `GET /books/9780451524935?format=json` | 200 JSON | 3 |
| `obtener_libro_format_xml` | `GET /books/9780451524935?format=xml` | 200 XML | 2 |
| `libro_inexistente` | `GET /books/0000000000000` | 404 | 1 |
| `conceptos_nube_xml` | `GET /cloud-concepts` | 200 XML | 2 |
| `conceptos_nube_json` | `GET /cloud-concepts?format=json` | 200 JSON | 2 |
| `conceptos_nube_format_xml` | `GET /cloud-concepts?format=xml` | 200 XML | 1 |
| `imagenes_xml` | `GET /books-images` | 200 XML | 2 |
| `imagenes_json` | `GET /books-images?format=json` | 200 JSON | 2 |
| `imagenes_format_xml` | `GET /books-images?format=xml` | 200 XML | 1 |
| `portada` | `GET /covers/9780451524935.svg` | 200 SVG | 2 |
| `portada_por_nombre` | `GET /covers/cover-9780451524935.png` | 200 SVG | 1 |

### Página y estáticos

| Tarea | Petición | Resultado válido | Peso |
| --- | --- | --- | --- |
| `indice_html` | `GET /` | 200 HTML | 1 |
| `indice_json` | `GET /?format=json` | 200 JSON | 1 |
| `indice_xml` | `GET /?format=xml` | 200 XML | 1 |
| `pagina_probar` | `GET /probar.html` | 200 HTML | 1 |
| `estilo_sitio` | `GET /site-style.css` | 200 CSS | 1 |
| `script_sitio` | `GET /site-js.js` | 200 JavaScript | 1 |
| `estilo_prueba` | `GET /css/probar.css` | 200 CSS | 1 |
| `script_soap` | `GET /js/soap-modulo.js` | 200 JavaScript | 1 |
| `wsdl` | `GET /soap` | 200 WSDL | 2 |
| `wsdl_alias` | `GET /wsdl` | 200 WSDL | 1 |
| `soap_info_json` | `GET /soap?format=json` | 200 JSON | 1 |

### SOAP (`POST /soap`)

| Tarea | Operación | Resultado válido | Peso |
| --- | --- | --- | --- |
| `on_start` | `RegistrarClasificacion` (una vez por usuario, correo nuevo) | 200 | — |
| `soap_conceptos_pendientes` | `ObtenerConceptosPendientes` | 200 | 2 |
| `soap_progreso` | `ObtenerProgresoUsuario` | 200 | 2 |
| `soap_estadisticas` | `ObtenerEstadisticasPorModelo` con `soap_stats` / `laboratorio` | 200 en modo demo | 1 |
| `soap_estadisticas_sin_credencial` | la misma operación, sin WS-Security | 401 | 1 |
| `soap_cuerpo_vacio` | cuerpo HTTP vacío | 400 | 1 |

### Escrituras

`POST`, `PUT` y `DELETE` de `/books` solo modifican el catálogo con `X-User-Role: admin` o `?role=admin`. Esta prueba no envía ese rol: un 403 con el texto `Se requiere usuario admin` es el resultado correcto. `POST /demo/reset` sí restaura la memoria de demostración cuando el servicio está en ese modo.

| Tarea | Petición | Resultado válido | Peso |
| --- | --- | --- | --- |
| `crear_libro_sin_admin` | `POST /books` | 403 | 1 |
| `reemplazar_libro_sin_admin` | `PUT /books/{isbn}` | 403 | 1 |
| `borrar_libro_sin_admin` | `DELETE /books/{isbn}` | 403 | 1 |
| `reiniciar_demo` | `POST /demo/reset` | 200 en demo, 404 si el modo demo está apagado | 1 |

## Cómo está armado `locustfile.py`

- **`UsuarioCatalogo`**: la clase `User`. Representa a un cliente virtual.
- **`on_start`**: se ejecuta una vez al nacer cada usuario. Aquí registra una clasificación SOAP.
- **`@task(n)`**: una acción. `n` es el peso. Locust elige al azar y favorece a las tareas de mayor peso. Las tres formas de `GET /books` pesan 6.
- **`wait_time = between(1, 2)`**: segundos de espera entre tareas.
- **`_marcar`**: decide si la respuesta cuenta como éxito. Un 403 en una escritura sin admin es éxito de la prueba. Un 500 en `GET /books` es fallo.
- **`abrir_interfaz`**: al ejecutar el archivo con Python, abre Locust en el puerto **8089** con 20 usuarios.

`_marcar`, `_get`, `_escribir_sin_admin`, `_post_soap` y `sobre_soap` son apoyo. Locust no las elige como comportamiento de usuario.
