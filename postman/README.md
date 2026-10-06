# Evidencia Postman · monorepo Librería

Necesitas **un solo collection** y **un environment**.

| Archivo | Qué es |
| --- | --- |
| `Libreria-monorepo.postman_collection.json` | Las 20 peticiones de evidencia (login + SOAP + Node) |
| `Libreria-local.postman_environment.json` | URLs locales `:5000` `:5001` `:3000` |

El login está en `services/login` (puerto 5000). El catálogo está en `services/books` (puerto 5001).

## 1. Levantar servicios (3 terminales)

Desde `/home/bold/Documents/Libreria`:

```bash
./run-login.sh      # login JSON  http://127.0.0.1:5000
./run-flask.sh      # SOAP/JSON   http://127.0.0.1:5001
./run-library.sh    # web Node    http://127.0.0.1:3000/library
```

Comprueba que responden:

```bash
curl -s 'http://127.0.0.1:5000/health?format=json'
curl -s 'http://127.0.0.1:5001/books?format=json' | head
curl -s 'http://127.0.0.1:3000/library/health'
```

## 2. Importar en Postman

1. Abre Postman → **Import** → arrastra los dos JSON de `postman/`.
2. Arriba a la derecha elige el environment **Librería local**.
3. En **Cookies** deja habilitado guardar cookies de `127.0.0.1` (hace falta para `/session`).

## 3. Qué peticiones fotografiar (evidencia)

Corre **en este orden**. En cada una: pestaña **Body → Pretty**, captura URL + status + JSON.

### Carpeta 1 · Login JSON :5000 (`services/login`)

| # | Petición | Status | Qué demuestra |
| --- | --- | --- | --- |
| 01 | `GET /?format=json` | 200 | HATEOAS, Richardson 3, sesión 30 min |
| 02 | `GET /health?format=json` | 200 | `postgres: ok` |
| 03 | `GET /captcha?format=json` | 200 | `question` tipo `3 + 4` y `captchaId` |
| 04 | `POST /register` **sin** captcha | 400 | el captcha es obligatorio |
| 05 | `POST /register` **con** captcha | 201 | `notification` JSON + `userExists: true` + token |
| 05b | `GET /account?email=...` | 200 | PostgreSQL: el usuario **existe**, correo no verificado |
| 06 | `POST /login` cuenta nueva | 403 | existe, pero `EMAIL_NOT_VERIFIED` |
| 07 | `GET /verify-email?token=...` | 200 | `notification.code: EMAIL_VERIFIED` |
| 07b | `GET /account?email=...` | 200 | el mismo usuario ya con `emailVerified: true` |
| 08 | `POST /login` cuenta nueva | 200 | sesión 30 min |
| 09 | `GET /session` | 200 | `authenticated: true` |
| 10 | `POST /session` | 200 | extiende 30 min |
| 11 | `POST /logout` | 200 | `authenticated: false` |
| 12 | `POST /login` admin | 200 | `mariana.solis@libreriaonline.mx` ya verificada |

Admin:

```json
{ "email": "mariana.solis@libreriaonline.mx", "password": "LibreriaAdmin26" }
```

### Carpeta 2 · Catálogo SOAP JSON :5001 (`services/books`)

| # | Petición | Status |
| --- | --- | --- |
| 01 | `GET /?format=json` | 200 |
| 02 | `GET /books?format=json` | 200 (≥ 30 libros) |
| 03 | `GET /books/9780451524935?format=json` | 200 (1984 + `coverUrl`) |
| 04 | `GET /books-images?format=json` | 200 |
| 05 | `GET /cloud-concepts?format=json` | 200 (IaaS PaaS SaaS FaaS) |
| 06 | `GET /soap?format=json` | 200 (operaciones SOAP) |

### Carpeta 3 · Librería Node :3000

| # | Petición | Nota |
| --- | --- | --- |
| 01 | `GET /library/health` | texto `OK` (no es JSON) |
| 02 | `GET /library/login` | HTML de la librería |

## 4. Reporte automático (todas las pruebas verdes)

En Postman: colección → **Run** → **Run Librería · evidencia JSON**.

O en terminal (con los 3 servicios arriba):

```bash
npx --yes newman run postman/Libreria-monorepo.postman_collection.json \
  -e postman/Libreria-local.postman_environment.json
```

Eso imprime cada request, el status y los tests. Captura el resumen final (`failed: 0`).

Reporte HTML (opcional):

```bash
npx --yes --package newman --package newman-reporter-htmlextra \
  newman run postman/Libreria-monorepo.postman_collection.json \
  -e postman/Libreria-local.postman_environment.json \
  -r cli,htmlextra \
  --reporter-htmlextra-export postman/evidencia.html
```

Abre `postman/evidencia.html` y captura el resumen en verde. Newman guarda las cookies de sesión durante la corrida; no hace falta cookie-jar.

## 5. Cómo se ve bien una captura

En Postman, para cada request:

1. Izquierda: nombre de la petición (01, 02, …).
2. Arriba: método + URL con `?format=json`.
3. Derecha: **200 / 201 / 400 / 403**.
4. Abajo: **Body → Pretty** con el JSON (`format: "json"`, `_links`, captcha, `emailVerified`, libros, etc.).

No uses la pestaña Preview ni XML: sin `format=json` el contrato Flask responde XML.
