# Módulo de microservicios — segundo parcial

Cuatro servicios, cada uno con su propia responsabilidad, su propio
contenedor y su propio contrato OpenAPI.

| Servicio | Responsable | Responsabilidad | Puerto en developer |
|---|---|---|---|
| `auth-service` | Integrante 1 | Emitir, renovar, validar y revocar tokens | 8101 |
| `users-service` | Integrante 1 | Usuarios, perfiles, permisos y alcance | 8102 |
| `documents-service` | Integrante 3 | Evidencias, avisos versionados y reportes | 8103 |
| `notifications-service` | Integrante 3 | Notificaciones internas | 8104 |

Cada uno expone:

- `GET /health/live` — el proceso responde
- `GET /health/ready` — sus dependencias responden
- `GET /openapi.json` — su contrato
- `GET /docs` — Swagger UI, servido por el propio servicio

## Levantar

```bash
cp infra/ambientes/developer.env.ejemplo infra/ambientes/developer.env

docker compose --env-file infra/ambientes/developer.env \
  -f infra/compose/docker-compose.base.yml \
  -f infra/compose/docker-compose.developer.yml \
  -f infra/compose/docker-compose.microservicios.yml up -d --wait
```

Después: <http://localhost:8101/docs>, `:8102`, `:8103`, `:8104`.

## Probar

```bash
python3 -m pytest pruebas/ -q      # 68 pruebas
```

La suite es repetible: limpia su propio estado en Redis al empezar.

## Lo que comparten

`comun/` es una librería instalada en cada imagen. Contiene la validación
de JWT contra Redis, el sobre de error, la serialización a JSON y XML, la
paginación, el límite de consumo, los endpoints de salud y el montaje de
Swagger.

Que sea compartida no es comodidad: si cada servicio escribiera su propia
validación de JWT, bastaría que uno la hiciera mal para abrir un hueco en
todo el módulo.

## Autenticación común

El sistema web y `auth-service` firman con el **mismo secreto** y comparten
la **misma instancia de Redis**. Por eso:

- un token emitido por cualquiera sirve en el otro;
- un `logout` revoca en todos los componentes a la vez;
- el sistema web sigue operando si los microservicios se caen.

Esa última propiedad se demuestra apagando un servicio y recargando
`/administracion/usuarios` en el portal: el aviso cambia de
«users-service» a «base de datos» y la tabla sigue mostrando los usuarios.
