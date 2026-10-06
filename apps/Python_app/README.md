# Cliente de escritorio (Python + Tkinter)

Aplicación en `apps/Python_app`. Consume los microservicios por HTTP y no abre PostgreSQL ni ninguna otra base.

| Pieza | Dónde está | Puerto |
| --- | --- | --- |
| Login | `services/login` | 5000 |
| Books | `services/books` | 5001 |
| Esta app | `apps/Python_app` | no escucha; es el cliente |

Login, books, users, authors, pedidos y pagos están en `services/`.

## Versión de Python

Python 3.10 o superior. Probado con el intérprete del sistema (3.14 en el equipo de desarrollo).

## Biblioteca gráfica

Tkinter, el toolkit que viene con Python. No hace falta PySide6.

## Dependencias

No hay paquetes de pip. `requirements.txt` lo deja escrito. Sí hace falta Tcl/Tk:

```bash
# Arch Linux
sudo pacman -S tk

# Debian/Ubuntu
sudo apt-get install -y python3-tk
```

En Windows 11, el instalador de python.org incluye Tcl/Tk si se deja marcada esa opción.

## Instalación

```bash
cd /ruta/al/repositorio
python3 --version
```

No hay `pip install`.

## Configuración

Al abrir la app, la pestaña **Configuración** permite:

- cambiar las URLs de login y books
- probarlas contra `GET /health`
- guardarlas
- restaurar `http://localhost:5000` y `http://localhost:5001`

El archivo queda en:

- Linux: `~/.config/libreria-python/config.json`
- Windows: `%APPDATA%\LibreriaPython\config.json`

La cookie de sesión va al lado, en `session-cookies.txt`. El JWT del login va en `jwt.txt`. No se guarda la contraseña.

Cada petición imprime una sola línea `evidencia` en la consola: método, URL, si va `Authorization: Bearer`, la contraseña como `***`, el código de respuesta y el HTTP. No imprime el JSON completo.

La misma pantalla sirve para la computadora local y para la IP de la instancia. No hay dos programas.

## Ejecución

En la raíz del repositorio, cada servicio en su terminal:

```bash
./run-login.sh      # http://localhost:5000
./run-flask.sh      # http://localhost:5001
./run-library.sh    # http://localhost:3000  (monolito; no lo usa esta app)
./run-tk.sh         # esta aplicación
```

O, ya dentro de la carpeta:

```bash
cd apps/Python_app
python3 app.py
```

Admin de demostración: `mariana.solis@libreriaonline.mx` / `LibreriaAdmin26`

## Estructura

| Archivo | Responsabilidad |
| --- | --- |
| `gui.py` | Pantallas: login, registro, perfil, catálogo, administración, estado, configuración |
| `config_store.py` | URLs y ruta local de la configuración |
| `http_api.py` | Peticiones HTTP, cookies, códigos y mensajes |
| `auth_api.py` | `/register`, `/verify`, `/login`, `/logout`, `/session`, `/session/extend`, `/profile` |
| `books_api.py` | `GET/POST/PUT/PATCH/DELETE /books` y el filtro de búsqueda |
| `health_api.py` | Verde, amarillo y rojo a partir de `/health` |
| `app.py` | Arranque |

## Microservicios que usa

Login:

- `POST /register`
- `GET /verify?token=`
- `POST /login`
- `POST /logout`
- `GET /session`
- `POST /session/extend`
- `PATCH /profile` con `Authorization: Bearer` (JWT del login)
- `GET /health`
- `GET /captcha` (el registro real lo exige)

Books:

- `GET /books?format=json`
- `GET /books/{isbn}`
- `POST /books` con `Authorization: Bearer`
- `PUT /books/{isbn}` reemplaza título, autores, categoría, año y precio. Exige el JWT
- `PATCH /books/{isbn}` envía un solo campo. Exige el JWT
- `DELETE /books/{isbn}` exige el JWT
- `GET /health`

Las altas y los cambios de books en modo demo viven en la memoria del proceso Flask. Si reinicias `./run-flask.sh`, el catálogo vuelve al de demostración.

## Problemas conocidos

- Las portadas del microservicio son SVG. Tkinter no las dibuja. La ficha muestra la referencia y, si no hay imagen, el texto «Sin imagen». No truena.
- El género solo aparece si el JSON del libro lo trae. Si no viene, la tabla dice «No informado».
- El CRUD de libros y el cambio de perfil exigen el JWT que devuelve el login. Buscar y consultar un libro siguen públicos.

## Solución de problemas

| Síntoma | Qué hacer |
| --- | --- |
| `No module named 'tkinter'` o falta `libtk` | Instala `tk` (Arch) o `python3-tk` (Debian) |
| Semáforo en rojo | El puerto o la IP de Configuración no coincide con el proceso. Prueba `curl` a `/health` |
| Semáforo en amarillo | El proceso responde y la base no. Revisa PostgreSQL del login (puerto 5433) |
| Al volver a abrir pide login | `GET /session` dijo que la cookie ya no vale. Es el comportamiento esperado |
| ISBN duplicado | El books responde 409. Cambia el ISBN |
| La ventana no abre en una VM | Hace falta escritorio o `ssh -X` |

## Evidencias

Las capturas, la bitácora y la reflexión las escribe quien ejecuta la app. No van en este código. Abajo está la lista de lo que hay que fotografiar.
