# Microservicio SOAP + JSON (librería EG02)

Flask bilingüe: **XML por defecto**, JSON con `?format=json`.

Ruta canónica: `app/services/soap/app.py`

SC3705 · Juan Pablo Ramos Salazar · 610248

## Arranque (desde la raíz del repo)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=app.py
flask run --host=0.0.0.0 --port=5001
```

| URL | Respuesta |
| --- | --- |
| `/books` | Catálogo EG02 en XML |
| `/books?format=json` | El mismo catálogo en JSON |
| `/books/9780451524935?format=json` | *1984* (Orwell) |
| `/cloud-concepts` | IaaS, PaaS, SaaS y FaaS con los libros |
| `/books-images` | ISBN, título e imagen de portada |
| `POST /soap` | Operaciones SOAP (Envelope XML) |

Sin `format`, todos los GET de datos responden XML. `POST /soap` siempre es SOAP/XML.

El módulo SOAP clasifica conceptos del **mismo catálogo** de `ejercicio02/library/` (vista `v_catalogo_conceptos`). No modifica las tablas del monolito Node.js.

```bash
cd app/services/soap
python -m pytest tests/ -q
```
