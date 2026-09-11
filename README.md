# Librería (Node :3000) + microservicio Flask (SOAP/XML/JSON :5001)

Son **dos procesos distintos**. Flask no corre la librería HTML.

| Puerto | Qué corre | Cómo se ve |
| --- | --- | --- |
| **3000** | Librería Node.js (Express + EJS): login, catálogo, alta/baja/cambio | http://127.0.0.1:3000/library |
| **5001** | Flask: SOAP, XML por defecto, JSON con `?format=json` | http://127.0.0.1:5001/books |

## Arranque de los dos

```bash
chmod +x run.sh run-flask.sh run-library.sh
./run.sh
```

O por separado, en dos terminales:

```bash
# Terminal 1 — Flask :5001 (SOAP + XML/JSON)
./run-flask.sh

# Terminal 2 — Librería :3000
./run-library.sh
```

La librería Node necesita PostgreSQL (`library_db`). Si no hay base, Flask en 5001 igual responde (modo demo). Postgres local:

```bash
cd ejercicio02/library
docker compose up -d
# luego carga db/01_schema.sql … db/06_views.sql contra library_db
```

## Flask :5001

```bash
export FLASK_APP=app.py
flask run --host=0.0.0.0 --port=5001
```

- http://127.0.0.1:5001/books — XML
- http://127.0.0.1:5001/books?format=json — JSON
- http://127.0.0.1:5001/books/9780451524935?format=json
- http://127.0.0.1:5001/cloud-concepts?format=json
- http://127.0.0.1:5001/books-images?format=json
- `POST http://127.0.0.1:5001/soap` — operaciones SOAP

CRUD JSON (admin):

```bash
curl -i -X POST 'http://127.0.0.1:5001/books?format=json' \
  -H 'Content-Type: application/json' -H 'X-User-Role: admin' \
  -d '{"isbn":"1234567890123","title":"Libro de prueba","category":"Prueba"}'
```

## Librería :3000

Cuentas de demostración:

- Admin: `mariana.solis@libreriaonline.mx` / `LibreriaAdmin26`
- Lector: `carlos.hernandez@gmail.com` / `Libreria2026`

## Carpetas

- `ejercicio02/library/` — librería Node en el puerto 3000
- `app/services/soap/` — Flask en el puerto 5001
