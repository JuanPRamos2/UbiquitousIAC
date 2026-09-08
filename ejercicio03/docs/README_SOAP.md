# library_soap_service

Módulo SOAP independiente del monolito Node.js. Clasifica conceptos del catálogo de la librería como IaaS, PaaS, SaaS o FaaS.

SC3705 · Juan Pablo Ramos Salazar · 610248

## Requisitos

- Python 3.10+
- PostgreSQL con el esquema del monolito ya aplicado (`ejercicio02/library/` + SQL del ejercicio 02)
- El código de `ejercicio02/library/` **no se modifica**

## Arranque local

Sin PostgreSQL el módulo entra en modo demostración (los mismos cuatro conceptos Cloud):

```bash
cd ejercicio03/library_soap_service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
# Interfaz: http://localhost:5000/
# WSDL:     http://localhost:5000/soap?wsdl
# POST:     http://localhost:5000/soap
pytest tests/ -q
```

En Ubiquitous la misma interfaz está en `ejercicio03/probar.html`.

Para usar el catálogo real de la librería, define `SOAP_DEMO=0` y las variables de `.env.example`.

El `.env.example` publicado no lleva un hash reutilizable. Genera el de laboratorio o de GCP con:

```bash
python -c "from soap.security import hash_password; print(hash_password('otra-clave'))"
```

## Contrato

| Operación | Header | Persistencia |
| --- | --- | --- |
| ObtenerConceptosPendientes | no | lectura catálogo + contador de cliente |
| RegistrarClasificacion | no | insert clasificación / Fault 409 |
| ObtenerProgresoUsuario | no | lectura |
| ObtenerEstadisticasPorModelo | WS-Security UsernameToken | lectura agregada |

## Privilegio mínimo (`soap_user`)

- SELECT: `books`, `concepts`, `book_concepts`, `categories`, `v_catalogo_conceptos`
- INSERT/UPDATE: `clasificadores`, `clasificaciones_cloud`, `clientes_servidos`
- Sin acceso a `users` (ni `password_hash`)

Despliegue en VM/GitHub/ubiquitous: `docs/INSTRUCCIONES_GCP_GITHUB.md`
