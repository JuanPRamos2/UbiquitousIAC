# UbiquitousIAC — monorepo

Aplicaciones, servicios, datos y código compartido en un solo repositorio.

## Arranque Flask (como en la terminal)

El comando `flask` no existe hasta activar el entorno virtual e instalar dependencias.

```bash
cd UbiquitousIAC
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export FLASK_APP=app.py
flask run --host=0.0.0.0 --port=5001
```

Luego:

| URL | Respuesta |
| --- | --- |
| http://127.0.0.1:5001/ | Interfaz SOAP |
| http://127.0.0.1:5001/soap | WSDL (GET) / SOAP (POST) |
| http://127.0.0.1:5001/books | Catálogo EG02 en **XML** |
| http://127.0.0.1:5001/books?format=json | Catálogo EG02 en **JSON** |
| http://127.0.0.1:5001/books/9780451524935?format=json | Libro *1984* en JSON |
| http://127.0.0.1:5001/cloud-concepts?format=json | IaaS, PaaS, SaaS y FaaS + libros |
| http://127.0.0.1:5001/books-images?format=json | Datos mínimos e imágenes |

Alta / cambio / baja del catálogo JSON (rol admin):

```bash
curl -X POST http://127.0.0.1:5001/books \
  -H 'Content-Type: application/json' -H 'X-User-Role: admin' \
  -d '{"isbn":"1234567890123","title":"Nuevo","category":"Prueba"}'

curl -X PUT http://127.0.0.1:5001/books/1234567890123 \
  -H 'Content-Type: application/json' -H 'X-User-Role: admin' \
  -d '{"title":"Nuevo título","category":"Prueba"}'

curl -X DELETE http://127.0.0.1:5001/books/1234567890123 \
  -H 'X-User-Role: admin'
```

## Estructura (Arquitectura de Monorepo)

```
UbiquitousIAC/
  apps/
    web-monolith/       librería Node.js (alta, baja, cambio)
    web-frontend/       vista del catálogo JSON
    desktop-app/        clasificador Java (EG03)
    mobile-app/         reserva
  services/
    service-catalogo/   Flask: SOAP + /books?format=json (reexporta app/services/soap)
    service-usuarios/
    service-pedidos/
    service-pagos/
  data/database/        schemas, seeds, migrations
  packages/
    api-contracts/      WSDL + OpenAPI
    shared-types/
    shared-ui/
    shared-utils/
  docs/architecture/
  .github/workflows/
  ejercicio01/ …        sitio Ubiquitous (HTML)
  app.py                FLASK_APP de la raíz (carga app/services/soap/app.py)
  app/services/soap/    microservicio Flask bilingüe XML/JSON + SOAP
```

## Sitio Ubiquitous

El HTML de evidencias sigue en la raíz (`index.html`, `ejercicio03/`) para
`https://ubiquitous.udem.edu/~iac-610248/`. Desde ahí se abre el SOAP y el catálogo JSON.

## Librería (CRUD por rol)

```bash
cd apps/web-monolith   # o ejercicio02/library
cp .env.example .env   # SESSION_SECRET y PostgreSQL
npm install
npm start
```

- **admin**: Alta, Cambio y Baja de libros.
- **lector / client**: solo consulta el catálogo.

Cuentas de demostración del EG02: `mariana.solis@libreriaonline.mx` (admin) y `carlos.hernandez@gmail.com` (lector).
