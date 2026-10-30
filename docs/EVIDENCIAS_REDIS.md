# Evidencia curl

Redis tiene que estar arriba:

```bash
docker compose -f apps/web-monolito/docker-compose.yml up -d redis
```

Variables de esta corrida:

```bash
BASE_LOGIN=http://127.0.0.1:5000
BASE_BOOKS=http://127.0.0.1:5001
BASE_USERS=http://127.0.0.1:5002
BASE_AUTHORS=http://127.0.0.1:5003
BASE_PEDIDOS=http://127.0.0.1:5004
BASE_PAGOS=http://127.0.0.1:5005
```

Admin: `mariana.solis@libreriaonline.mx` / `LibreriaAdmin26`

## 1. Health con Redis

```bash
curl -sS "$BASE_LOGIN/health?format=json"
curl -sS "$BASE_BOOKS/health?format=json"
curl -sS "$BASE_USERS/health"
curl -sS "$BASE_AUTHORS/health"
curl -sS "$BASE_PEDIDOS/health"
curl -sS "$BASE_PAGOS/health"
curl -sS "$BASE_BOOKS/metrics?format=json"
```

Login y los servicios que autorizan deben mostrar `"redis":"ok"`. Si Redis está apagado, login responde 503 y un GET de books sigue en 200 con `"redis":"error"`.

## 2. Login, JWT de 20 minutos y refresh

```bash
curl -sS -c /tmp/libreria.cookies -D - \
  -H 'Content-Type: application/json' \
  -d '{"email":"mariana.solis@libreriaonline.mx","password":"LibreriaAdmin26"}' \
  "$BASE_LOGIN/login?format=json"
```

La respuesta trae `token`, `tokenExpiresAt` y `refreshToken`. No se imprimen en el log de la app Tk. Para renovar antes de que caduque:

```bash
curl -sS -H 'Content-Type: application/json' \
  -d '{"refreshToken":"<refresh>"}' \
  "$BASE_LOGIN/token/refresh?format=json"
```

## 3. Caché del catálogo

```bash
curl -sS -D - -o /dev/null "$BASE_BOOKS/books?format=json"
curl -sS -D - -o /dev/null "$BASE_BOOKS/books?format=json"
curl -sS -D - -o /dev/null "$BASE_BOOKS/books/9780451524935?format=json"
```

La primera respuesta lleva `X-Cache: MISS`. La segunda, `X-Cache: HIT`. Después de un POST, PUT, PATCH o DELETE el siguiente GET vuelve a `MISS`.

Sin token, una escritura responde 401:

```bash
curl -sS -D - -H 'Content-Type: application/json' \
  -d '{"isbn":"111","title":"X"}' \
  "$BASE_BOOKS/books?format=json"
```

## 4. Users

Sin JWT:

```bash
curl -sS -D - "$BASE_USERS/users"
```

Esperado: 401.

Con el access token del admin:

```bash
curl -sS -H "Authorization: Bearer <token>" "$BASE_USERS/users"
```

Cambiar el correo debe rechazarse. La contraseña exige tres valores:

```bash
curl -sS -D - -H "Authorization: Bearer <token>" -H 'Content-Type: application/json' \
  -d '{"currentPassword":"LibreriaAdmin26","newPassword":"LibreriaAdmin27","confirmPassword":"OtraDistinta27"}' \
  "$BASE_USERS/users/1/password"
```

Si la confirmación no coincide, la respuesta es 400 y el hash no cambia.

## 5. Autores

```bash
curl -sS "$BASE_AUTHORS/authors"
curl -sS -D - -H 'Content-Type: application/json' -d '{"nombre":"Sin token"}' "$BASE_AUTHORS/authors"
```

El GET es público. El POST sin Bearer es 401. Con un JWT que no sea admin, 403.

## 6. Pedidos y pagos

```bash
curl -sS -D - "$BASE_PEDIDOS/pedidos"
curl -sS -D - -H "Authorization: Bearer <token>" -H 'Content-Type: application/json' \
  -d '{"lines":[{"isbn":"9780451524935","quantity":1}]}' \
  "$BASE_PEDIDOS/pedidos"
```

El alta descuenta stock. Cancelar con `DELETE /pedidos/{id}` lo devuelve si el pedido sigue pendiente.

```bash
curl -sS -D - -H "Authorization: Bearer <token>" -H 'Content-Type: application/json' \
  -d '{"order_id":1,"amount":0,"method":"efectivo"}' \
  "$BASE_PAGOS/pagos"
```

El monto tiene que ser el total del pedido. Si coincide, el pedido queda `pagado`.

## 7. Logout y revocación

```bash
curl -sS -b /tmp/libreria.cookies -H "Authorization: Bearer <token>" \
  -X POST "$BASE_LOGIN/logout?format=json"
curl -sS -D - -H "Authorization: Bearer <token>" -H 'Content-Type: application/json' \
  -d '{"nombre":"No debe"}' \
  "$BASE_USERS/users/1"
```

El segundo llamado, con el mismo access token, responde 401 y `TOKEN_REVOKED`.

La colección de Postman está en `postman/Libreria-redis.postman_collection.json`.
La app Tk se abre con `./run-tk.sh`: semáforos de los seis servicios, radio HTTP/HTTPS y pestañas de libros, usuarios, autores, pedidos y pagos.

## Corrida registrada

`docs/evidencias/curl-salida.txt` guarda 44 peticiones de una corrida real contra los seis servicios. Los JWT y el refresh quedan como `<redactado>`.

| Paso | Resultado |
| --- | --- |
| Health de login, books, users, autores, pedidos y pagos | 200, postgres y redis en ok |
| GET /users y POST /books sin Bearer | 401 TOKEN_MISSING |
| GET /books y GET /books/{isbn} | X-Cache MISS y después HIT |
| POST /books y el GET siguiente | 201 e invalidación, X-Cache MISS |
| PATCH de correo y confirmación de contraseña distinta | 400 |
| Alta de cliente y POST /authors con ese JWT | 201 y 403 |
| Pedido, pago con monto distinto, pago correcto, cancelar pagado, borrar pago, cancelar | 201, 400, 201, 409, 200, 200 |
| POST /token/refresh y el JWT anterior | 200 y 401 TOKEN_REVOKED |
| POST /logout y el JWT nuevo | 200 y 401 TOKEN_REVOKED |
