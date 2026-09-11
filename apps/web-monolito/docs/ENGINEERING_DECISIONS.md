# Decisiones de ingeniería

Esquema usado: **necesidad → alternativas → decisión → justificación → riesgo → evidencia**.

## D1. Monolito server-side

- **Necesidad:** Una sola aplicación de librería, con formularios HTML, un equipo pequeño y una instancia de ejercicio.
- **Alternativas:** SPA + API REST; microservicios por catálogo; monolito modular server-side.
- **Decisión:** Monolito Express + EJS. Una unidad desplegable. Carpetas internas para separar responsabilidades.
- **Justificación:** El enunciado prohíbe APIs y pide HTML generado en el servidor. Un monolito reduce superficie de red, sesiones y despliegue. Modularizar no lo convierte en sistema distribuido: no hay límites de proceso ni contratos entre servicios.
- **Riesgo:** El crecimiento futuro de equipos o de canales (móvil, partners) tensionaría este corte. Entonces sí convendría desacoplar.
- **Evidencia:** `app.js` monta un único router en `/library`; no existen controladores JSON.

## D2. Acceso directo a PostgreSQL

- **Necesidad:** Persistir un modelo 4FN con integridad referencial y la regla de un solo administrador.
- **Alternativas:** ORM; API de datos intermedia; SQL parametrizado + stored procedures.
- **Decisión:** Controlador `pg`, consultas parametrizadas y SP en `db/04_stored_procedures.sql`.
- **Justificación:** Permite demostrar PK/FK/CHECK/índices y pruebas negativas reales de PostgreSQL. El ORM ocultaría las restricciones que el ejercicio pide defender.
- **Riesgo:** Más SQL manual y duplicación si el modelo crece. Mitigación: servicios delgados que llaman SP.
- **Evidencia:** `config/db.js` + `services/*.js` usan `$1, $2…` o `SELECT * FROM sp_…($1)`.

## D3. Renderizado EJS en el servidor

- **Necesidad:** Intercambiar datos sin JSON/XML entre frontend y backend.
- **Alternativas:** React/Vue; plantillas EJS; htmx sobre JSON.
- **Decisión:** EJS + `application/x-www-form-urlencoded` y `multipart/form-data`.
- **Justificación:** El navegador envía formularios al monolito y recibe HTML. Cumple la restricción arquitectónica y simplifica CSRF relativo a una API pública (sigue existiendo riesgo de CSRF clásico; las cookies son `SameSite=Lax`).
- **Riesgo:** Menos interactividad. Aceptable para un CRUD académico.
- **Evidencia:** `views/**/*.ejs` y ausencia de `res.json` en rutas de negocio.

## D4. Un administrador en aplicación y en BD

- **Necesidad:** RF-20.
- **Alternativas:** Solo middleware; solo UI oculta; índice único parcial + trigger.
- **Decisión:** Índice `ux_users_single_admin` y trigger `trg_users_single_admin`.
- **Justificación:** La UI puede fallar o ser eludida. La BD es la última línea de defensa.
- **Riesgo:** Operación de emergencia si se pierde el admin (hay que promover con un procedimiento controlado).
- **Evidencia:** `db/01_schema.sql`, `db/05_triggers.sql`, prueba negativa en el plan de pruebas.

## D5. Imágenes en disco, metadatos en PostgreSQL

- **Necesidad:** Portadas y galería sin guardar BLOBs pesados en la BD del ejercicio.
- **Alternativas:** BYTEA; object storage; disco local + metadatos.
- **Decisión:** `uploads/` con nombre generado; tabla `images` con `stored_name`, MIME, tamaño y alt.
- **Justificación:** Encaja en una VM única. No se reutiliza el nombre original del usuario.
- **Riesgo:** Backup incompleto si solo se respalda PostgreSQL. Documentado como limitación.
- **Evidencia:** `config/upload.js`, `sp_add_book_image`.

## Condiciones futuras de cambio

| Decisión | Cambiaría si… |
| --- | --- |
| Monolito | Hubiera un segundo canal (app móvil) o dos equipos desplegando con cadencias distintas. |
| SQL directo | El modelo superara ~40 entidades y el costo de mantenimiento SQL fuera mayor que el de un ORM. |
| EJS | Se necesitara UI rica desconectada del ciclo request/response. |
