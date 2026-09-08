# Librería en línea — Ejercicio guiado 02

Aplicación web **monolítica** y **server-side** (Node.js + Express + EJS + PostgreSQL) para gestión de una librería.

Estudiante: Juan Pablo Ramos Salazar · Matrícula 610248

## Qué es y qué no es

- Sí: HTML renderizado en el servidor, formularios POST, consultas SQL parametrizadas y stored procedures.
- No: APIs REST/GraphQL/SOAP, JSON/XML como intercambio frontend-backend, microservicios.

La interfaz, la lógica de negocio y el acceso a datos se despliegan juntos. La organización en carpetas no convierte esto en una arquitectura distribuida.

## Estructura

```
library/
  app.js                 Inicialización de Express, sesión, montaje en /library
  config/                Conexión PostgreSQL y carga de imágenes
  routes/                Recepción HTTP y coordinación
  services/              Reglas de aplicación y llamadas a SQL/SP
  middleware/            Auth, autorización, validación, errores
  views/                 Plantillas EJS (sin SQL)
  public/                CSS e imagen de respaldo
  uploads/               Archivos subidos (nombre generado por el sistema)
  db/                    Scripts 00 a 06
  docs/                  Decisiones, requisitos, seguridad, pruebas, GCP
```

## Base de datos

En el servidor (usuario privilegiado, no el de la aplicación):

```bash
sudo -u postgres psql -f db/00_create_database.sql
sudo -u postgres psql -d library_db -f db/01_schema.sql
sudo -u postgres psql -d library_db -f db/02_seed_30_per_table.sql
sudo -u postgres psql -d library_db -f db/03_all_quieries_before_stored_procedures.sql
sudo -u postgres psql -d library_db -f db/04_stored_procedures.sql
sudo -u postgres psql -d library_db -f db/05_triggers.sql
sudo -u postgres psql -d library_db -f db/06_views.sql
```

Después otorgue privilegios mínimos al usuario `library_user` (véase comentarios en `db/00_create_database.sql`).

## Aplicación en CentOS Stream 10

1. Instale Node.js 20+ y clone/copie este directorio.
2. Copie `.env.example` a `.env` y asigne secretos. **No publique `.env`.**
3. `npm install --omit=dev`
4. `npm start`  → escucha **solo** en `127.0.0.1:3000`
5. Prueba local: `http://127.0.0.1:3000/library`
6. Publique `/library` con Apache o NGINX (archivos en `docs/deploy/`).

Cuentas de demostración:

- Administradora: `mariana.solis@libreriaonline.mx` / `LibreriaAdmin26`
- Lector: `carlos.hernandez@gmail.com` / `Libreria2026`

## Restricciones de seguridad aplicadas

- Hash bcrypt de contraseñas
- Un solo Administrador (índice único + trigger)
- Middleware de autenticación y autorización
- Validación server-side
- Uploads con MIME, extensión, tamaño y nombre generado
- Errores controlados (sin SQL ni stack al usuario)
- Node no se expone a Internet; reverse proxy hacia localhost
