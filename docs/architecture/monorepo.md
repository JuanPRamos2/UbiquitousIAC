# Arquitectura de monorepo

Necesidad → un solo repositorio para el sitio Ubiquitous, la librería, el módulo SOAP y el catálogo JSON.
Decisión → carpetas `apps/`, `services/`, `data/`, `packages/`, `docs/` y `.github/` como en el diagrama de clase.
Justificación → cada pieza tiene dependencias propias y se habla por contrato (WSDL / OpenAPI / `?format=json`).
Ventajas → un `git clone` trae todo; Flask se arranca desde la raíz.
Limitaciones → Apache en Ubiquitous no ejecuta Flask; el servicio corre en local o en una VM (`flask run --port=5001`).

Comunicación:

```
Sitio Ubiquitous (HTML)
  → ejercicio03/probar.html  → Flask POST /soap
  → ejercicio03/catalogo.html → Flask GET /books?format=json

Librería (apps/web-monolith)
  → PostgreSQL (data/database)
  → admin: alta / cambio / baja
  → lector: consulta

Cliente Java (apps/desktop-app)
  → Flask POST /soap
```
