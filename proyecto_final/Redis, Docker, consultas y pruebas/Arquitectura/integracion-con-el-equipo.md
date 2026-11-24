# Contrato para integrar a los integrantes 1, 2 y 3

Este archivo sale del PDF `Division_trabajo_segundo_parcial.pdf` y del código que ya está en `proyecto_final`. La parte 4 no sustituye el trabajo de los otros tres. Les deja la red, Redis y el formato del token para que sus servicios entren después.

## Quién hace qué

| Integrante | Servicios | Qué debe conservar para que la parte 4 siga funcionando |
| --- | --- | --- |
| 1 | `auth-service` y `users-service`, más la ampliación de la web | El JWT con `sub`, `perfil` y `jti`. Al entrar, `session:{jti}` en Redis. Al salir, `revoked:{jti}` y borrar la sesión. Mismo `JWT_SECRET`. |
| 2 | `main-process-service` y `catalog-service`, PostgreSQL y MongoDB | Las tablas y vistas que consultas y reportes ya leen. Si publica filas en `agregado.resultado_protegido`, la gráfica de valor protegido las toma sola. |
| 3 | `documents-service` y `notifications-service`, y el estándar JSON/XML/XSD/Swagger del equipo | Puede adoptar el sobre que ya usan consultas y reportes, o avisar un cambio. El punto único de cambio es `services/comun/src/http.js` y `services/comun/src/xml.js`. |
| 4 | `queries-service` y `reports-service`, Redis, Docker y pruebas de integración | Ya está hecho. No recalcula el agregado con ruido, porque eso gasta el presupuesto de privacidad y es del proceso principal. |

La segunda entrega no pide aplicación Android ni de escritorio. Sí pide que JSON y XML queden implementados. En consultas y reportes ya se puede pedir y responder en los dos formatos.

## Nombres en Docker

La red se llama `nexum`. Entre contenedores no se usa `localhost`.

| Servicio | Dueño | Nombre DNS | Hoy |
| --- | --- | --- | --- |
| Web | 1 | `web` o `api` | Monolito, puerto interno 3000, host 3001 |
| Auth | 1 | `auth-service` | `POST http://api:3000/api/auth/login` |
| Usuarios | 1 | `users-service` | Rutas de usuarios del monolito |
| Catálogo | 2 | `catalog-service` | `/api/catalogos` del monolito |
| Proceso principal | 2 | `main-process-service` | Encuestas y cálculo protegido en PostgreSQL |
| Documentos | 3 | `documents-service` | Aún no hay contenedor propio |
| Notificaciones | 3 | `notifications-service` | Aún no existe |
| Consultas | 4 | `queries-service` | Host 3010 |
| Reportes | 4 | `reports-service` | Host 3020 |
| PostgreSQL | 2, usado por todos | `postgres` | 5432 en la red, 5433 en el host |
| MongoDB | 2, usado por todos | `mongo` | 27017 |
| Redis | 4, usado por todos | `redis` | 6379 |

Para colgar un servicio nuevo hacen falta su `Dockerfile` y un bloque en `docker-compose.yml` con `networks: [nexum]`, `REDIS_URL=redis://redis:6379`, `POSTGRES_HOST=postgres` y `MONGO_URL=mongodb://mongo:27017`.

## Lo que el integrante 1 debe escribir en Redis

```text
session:{jti}     hash o string, TTL = vida del JWT
revoked:{jti}     string "1", TTL = segundos que le quedan al token
```

Consultas y reportes ya rechazan el token si la sesión no existe o si `revoked:{jti}` existe. El código está en `services/comun/src/jwt.js`. Los otros servicios protegidos pueden usar ese mismo archivo.

Perfiles válidos: `COLABORADOR`, `LIDER`, `ESPECIALISTA`, `AUDITOR`, `ADMINISTRADOR`.

## Lo que el integrante 2 no debe romper

Consultas y reportes leen, entre otras:

- `catalogo.campania`
- `organizacion.unidad_organizacional`
- `intervencion.plan`
- `auditoria.v_tablero_auditoria`
- `agregado.v_tablero_unidad`
- `agregado.v_tendencia`
- `agregado.resultado_protegido`
- colección MongoDB `solicitudes_apoyo` (`mensaje`, `estado`, `fecha`; el seudónimo no se devuelve)

No llaman a `agregado.fn_calcular_agregado_protegido`.

## Lo que el integrante 3 puede tomar como contrato

Éxito JSON:

```json
{
  "success": true,
  "message": "...",
  "data": {},
  "pagination": { "page": 1, "limit": 20, "total": 0, "totalPages": 0 }
}
```

Error JSON:

```json
{
  "success": false,
  "error": { "code": "NO_ENCONTRADO", "message": "...", "details": {} }
}
```

XML: el mismo contenido bajo `<response>`, pidiendo `Accept: application/xml`. Los XSD están en `services/comun/xsd/` y en `GET /api/v1/xsd/`.

Swagger de esta parte:

- http://127.0.0.1:3010/api/docs
- http://127.0.0.1:3020/api/docs

El integrante 3 documenta el estándar del equipo y sus dos servicios. El Swagger de consultas y reportes ya ejecuta peticiones reales.
