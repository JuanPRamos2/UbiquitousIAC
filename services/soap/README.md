# Microservicio SOAP + XML/JSON

Código canónico: `services/soap/`. La práctica también pide `app/services/soap/app.py`; ese archivo **carga este mismo Flask**.

```bash
# desde la raíz del monorepo
./run-flask.sh
# o:
SOAP_DEMO=1 PYTHONPATH=services/soap python3 app/services/soap/app.py
```

Sin `format` → XML. Con `?format=json` → JSON.
`GET /books` incluye portada (`coverUrl`), año y **precio**.
`GET /books-images` datos mínimos + imágenes.
`POST /soap` → Envelope SOAP.
