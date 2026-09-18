# Revisión de seguridad

Cada control: amenaza, mitigación, evidencia.

| Control | Amenaza | Control aplicado | Evidencia de prueba |
| --- | --- | --- | --- |
| Hash de contraseñas | Robo de BD con claves en claro | bcrypt (coste 10); política: 8+ caracteres, letras y números | Registro + inspección de `password_hash` en `psql` |
| Secretos en entorno | Credenciales en git o ubiquitous | `.env` gitignored; `.env.example` sin valores | `git status` no lista `.env`; grep no encuentra claves reales en docs |
| SQL parametrizado | SQL Injection | `$n` y SP; sin concatenar input en SQL | Búsqueda con `' OR 1=1 --` no altera el predicado |
| Validación server-side | Bypass de HTML5 | `middleware/validate.js` + CHECK en PostgreSQL | POST de stock `-1` rechazado |
| Autorización por rol | Cliente en rutas admin | `requireAdmin` + 403 | Usuario `client` en `/library/books/new` ve 403 |
| Sesiones | Robo o fijación de sesión | `httpOnly`, `sameSite=lax`, path `/library`, logout destruye sesión | Tras logout, `/library/books` redirige a login |
| Uploads | Web shell o archivo enorme | MIME allowlist, extensión, 5 MB, nombre aleatorio | `.php` rechazado; JPG aceptado con nombre generado |
| Errores controlados | Fuga de SQL/stack | `errorHandler` no envía `err.stack` ni SQL | Forzar error de FK muestra mensaje genérico |
| Mínimo privilegio BD | Superusuario comprometido | Rol `library_user` sin CREATEDB/SUPERUSER | `\du` muestra atributos limitados |
| Un administrador | Escalada de privilegios | Índice único + trigger | INSERT de segundo admin falla |
| Node en localhost | Exposición directa del puerto 3000 | `listen(3000, '127.0.0.1')` | `ss -lptn` muestra 127.0.0.1:3000 |
| No publicar secretos | Fuga en tar.gz / página | Excluir `.env`, `node_modules`, llaves | Checklist de empaquetado en README |

## Riesgo residual

- CSRF sobre formularios autenticados (SameSite=Lax reduce el caso GET cross-site; un POST cross-site desde otro sitio aún es un riesgo residual).
- Las imágenes seed no viven en disco; las reales sí. Un backup solo de PostgreSQL pierde archivos.
- TLS depende del reverse proxy; Node no termina HTTPS.
