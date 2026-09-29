# Login (Flask + PostgreSQL)

Microservicio independiente de autenticación en **http://127.0.0.1:5000**.

XML por defecto. JSON sólo con `?format=json`. Swagger en `/docs`.

```bash
# desde la raíz del monorepo
./run-login.sh
```

O:

```bash
cd apps/services/login
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

| Recurso | Uso |
| --- | --- |
| GET `/account?email=` | JSON: si el usuario existe en PostgreSQL y si el correo ya está verificado |
| POST `/register` | Alta con nombre, apellidos, email único y captcha. Devuelve `notification` JSON (el “correo” de verificación) |
| POST `/login` | Autentica contra PostgreSQL y abre sesión Flask de 30 min |
| POST `/logout` | Cierra la sesión |
| GET `/session` | Estado, restante y aviso para extender |
| POST `/session` | Extiende 30 minutos (HATEOAS) |
| GET `/health` | Servicio + PostgreSQL |
| PATCH `/profile` | Actualiza atributos. Exige `Authorization: Bearer` con un JWT de este servicio |
| GET `/docs` | Swagger UI |
| GET `/ui` | Pantalla de login en JSON |

`POST /login` y la verificación de correo siguen públicos. Si las credenciales son válidas, la respuesta incluye `token`, `tokenType` (`Bearer`) y `tokenExpiresAt`. La contraseña del usuario se guarda solo como `password_hash` (bcrypt). El JWT se firma con PyJWT (HS256) usando el hash SHA-256 de `JWT_PASSWORD`, la misma contraseña compartida con el microservicio de libros.

Si el token falta, está mal formado, expiró o no lo emitió este login, la respuesta es HTTP 401 con `code` `TOKEN_MISSING`, `TOKEN_MALFORMED`, `TOKEN_EXPIRED` o `TOKEN_INVALID`.

La contraseña se guarda sólo como `users.password_hash` (bcrypt). No hay tabla de passwords.
