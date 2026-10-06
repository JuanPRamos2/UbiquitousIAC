# Microservicios

Los seis viven aquí: `login` (5000), `books` (5001), `users` (5002), `authors` (5003), `pedidos` (5004) y `pagos` (5005). Comparten `services/shared` (Redis, JWT y CORS). `app/services/soap/app.py` solo carga `services/books`.

```bash
./run-all.sh
```

Ese comando arranca los seis y deja en la terminal el nombre, el puerto y si está corriendo. `Ctrl+C` los detiene.

`GET /books` y `GET /books/{isbn}` son públicos y se cachean en Redis (`books:list:<filtros>`, `books:<isbn>`, TTL corto). Si Redis no responde, la lectura sigue y el encabezado `X-Cache` dice `BYPASS`. `POST`, `PUT`, `PATCH` y `DELETE` exigen `Authorization: Bearer` de un administrador, comprueban `jwt:revoked:<jti>` y borran la caché. Si Redis no puede confirmar la revocación, la escritura responde 503.

No se llaman entre sí. PostgreSQL sigue siendo la fuente de verdad y Redis guarda sesión, revocación y caché.

- http://127.0.0.1:5001/books — XML
- http://127.0.0.1:5001/books?format=json — JSON
- POST http://127.0.0.1:5001/soap — SOAP
