# Ejercicio guiado 02 — Integración de Aplicaciones Computacionales

- Reporte: `index.html`
- Librería usable en ubiquitous (HTML/JS): `html/libreria.html`
- Monolito Node + PostgreSQL (VM / GCP): `library/`
- SQL de entrega: `sql/`
- Documentos: `docs/`

## En ubiquitous

Copiar el sitio completo (`UbiquitousIAC/`) a `~/html/` (o el directorio que asigne el curso), de modo que quede:

`https://ubiquitous.udem.edu/~iac-610248/ejercicio02/`

La librería se abre en `ejercicio02/html/libreria.html`. Apache no ejecuta Node; por eso esa versión corre en el navegador.

**No subir:** `library/.env`, `library/node_modules/`, `library/uploads/*` con archivos reales de prueba, ni llaves SSH.

Los `.htaccess` de esta entrega **no usan `Options`**: en ubiquitous esa directiva provoca HTTP 500 en todo el ejercicio. `library/.htaccess` solo niega el acceso al monolito si la carpeta se copia por error.

## En la VM (entrega del monolito)

Ver `library/README.md`. Escucha en `127.0.0.1:3000/library` detrás de Apache o NGINX.
