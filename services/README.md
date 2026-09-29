# SOAP Flask

Microservicio bilingüe. Código en `services/soap/` (no en `app/`).

```bash
./run-flask.sh
```

`GET /books` y `GET /books/{isbn}` son públicos. `POST`, `PUT`, `PATCH` y `DELETE` exigen `Authorization: Bearer` con un JWT emitido por el login (`JWT_PASSWORD` compartida, PyJWT HS256).

- http://127.0.0.1:5001/books — XML
- http://127.0.0.1:5001/books?format=json — JSON
- POST http://127.0.0.1:5001/soap — SOAP
