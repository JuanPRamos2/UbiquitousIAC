# Organización del código (MVC server-side)

| Elemento | Responsabilidad |
| --- | --- |
| `app.js` | Express, sesión, estáticos, montaje en `/library`, listen en 127.0.0.1 |
| `config/` | Pool PostgreSQL y política de uploads |
| `routes/` | HTTP: interpreta el formulario, llama servicios, elige la vista |
| `services/` | Reglas de aplicación y llamadas a SP/SQL parametrizado |
| `middleware/` | Authn, authz, flash, validación, errores |
| `views/` | EJS. Sin SQL y sin reglas de negocio |
| `public/` | CSS y placeholder |
| `uploads/` | Binarios subidos, nombre generado |
| `db/` | Fuente de verdad del modelo |
| `docs/` | Decisiones y evidencias de ingeniería |

Las vistas no consultan PostgreSQL. `app.js` no contiene CRUD. Las rutas no arman SQL concatenado.
