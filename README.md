# Librería (catálogo + microservicio Flask)

Proyecto de la librería: catálogo de libros del Ejercicio 02 y microservicio Flask bilingüe (XML/JSON) + SOAP.

No incluye el sitio Ubiquitous (HTML de evidencias de la materia).

## Arranque Flask

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=app.py
flask run --host=0.0.0.0 --port=5001
```

| URL | Qué es |
| --- | --- |
| http://127.0.0.1:5001/books | Catálogo XML |
| http://127.0.0.1:5001/books?format=json | Catálogo JSON |
| http://127.0.0.1:5001/books/9780451524935?format=json | *1984* |
| http://127.0.0.1:5001/cloud-concepts?format=json | IaaS, PaaS, SaaS, FaaS |
| http://127.0.0.1:5001/books-images?format=json | Libros + portadas |
| POST/PUT/DELETE `/books` | Alta / cambio / baja (header `X-User-Role: admin`) |
| POST http://127.0.0.1:5001/soap | Operaciones SOAP |

## Carpetas

- `app/services/soap/` — microservicio Flask (canónico)
- `ejercicio02/library/` — librería Node.js (alta, baja, cambio)
- `ejercicio03/library_soap_service/` — copia SOAP de compatibilidad
- `apps/web-monolith/` — misma librería Node en el monorepo

## CRUD rápido

```bash
curl -i -X POST 'http://127.0.0.1:5001/books?format=json' \
  -H 'Content-Type: application/json' -H 'X-User-Role: admin' \
  -d '{"isbn":"1234567890123","title":"Libro de prueba","category":"Prueba"}'
```
