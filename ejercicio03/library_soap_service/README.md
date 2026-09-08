# library_soap_service

Copia de compatibilidad del microservicio Flask. La implementación canónica está en:

`app/services/soap/app.py`

Clasifica conceptos del catálogo de la librería del EG02 como IaaS, PaaS, SaaS o FaaS y publica el mismo catálogo en XML/JSON.

SC3705 · Juan Pablo Ramos Salazar · 610248

## Arranque (preferido, raíz del repo)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=app.py
flask run --host=0.0.0.0 --port=5001
```

También se puede ejecutar este directorio:

```bash
cd ejercicio03/library_soap_service
python app.py
```

Sin `?format=` las respuestas de datos son XML. Con `?format=json` son JSON.

El código de `ejercicio02/library/` **no se modifica**.
