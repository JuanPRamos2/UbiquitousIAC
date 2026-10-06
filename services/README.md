# SOAP Flask

Microservicio bilingüe. Código en `services/soap/` (no en `app/`).

```bash
./run-flask.sh
```

`GET /books` y `GET /books/{isbn}` son públicos y se cachean en Redis (`books:list:<filtros>`, `books:<isbn>`, TTL corto). Si Redis no responde, la lectura sigue y el encabezado `X-Cache` dice `BYPASS`. `POST`, `PUT`, `PATCH` y `DELETE` exigen `Authorization: Bearer` de un administrador, comprueban `jwt:revoked:<jti>` y borran la caché. Si Redis no puede confirmar la revocación, la escritura responde 503.

Los otros microservicios están en `services/users` (5002), `services/authors` (5003), `services/pedidos` (5004) y `services/pagos` (5005). Comparten `JWT_SECRET_KEY` y `REDIS_URL`. No se llaman entre sí: PostgreSQL sigue siendo la fuente de verdad.

- http://127.0.0.1:5001/books — XML
- http://127.0.0.1:5001/books?format=json — JSON
- POST http://127.0.0.1:5001/soap — SOAP
