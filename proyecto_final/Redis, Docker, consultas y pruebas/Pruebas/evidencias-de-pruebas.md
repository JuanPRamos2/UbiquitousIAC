# Evidencias de requests y de Redis

Las pruebas de integración (`INTEGRACION=1 npm run test:integracion`) ya ejercitaron estos casos contra los contenedores y quedaron en verde. Abajo está el guion para repetirlos delante del profesor y la lista de pantallas que hay que capturar.

Sustituye el puerto 3001 si tu `.env` publica la web en 3000. El token sale del login real del monolito.

```bash
curl -s -X POST http://127.0.0.1:3001/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"correo":"mariana.solis@nexum.com.mx","contrasena":"demo123"}'
```

Guarda el campo `token`. En los ejemplos, `$TOKEN`.

## Consultas — éxito, caché y Redis

- Método: GET
- URL: `http://127.0.0.1:3010/api/v1/queries/campanias?estado=ABIERTA&limit=2`
- Headers: `Authorization: Bearer $TOKEN` y `Accept: application/json`
- Body: ninguno
- HTTP 200
- Qué hace: lista campañas abiertas desde `catalogo.campania`
- Primera vez: `meta.cache` = `MISS`. Log: `CACHE MISS`
- Segunda vez igual: `meta.cache` = `HIT`. Log: `CACHE HIT`
- Redis: `GET` de `meta.clave_cache` devuelve el JSON. `TTL` de esa clave es un entero positivo, como máximo `CACHE_TTL_SEC`
- PostgreSQL: `SELECT campania_id, estado FROM catalogo.campania WHERE estado = 'ABIERTA';` devuelve `CAMP-2026-S4`

Respuesta real observada:

```json
{
  "success": true,
  "message": "Campañas consultadas",
  "data": {
    "campanias": [{
      "campania_id": "CAMP-2026-S4",
      "nombre": "Medicion semana 4",
      "estado": "ABIERTA",
      "fecha_inicio": "2026-08-24",
      "fecha_fin": "2026-08-28",
      "secuencia": 4
    }]
  },
  "pagination": { "page": 1, "limit": 2, "total": 1, "totalPages": 1 },
  "meta": { "cache": "HIT", "servicio": "queries-service" }
}
```

## Consultas — XML

- Igual que la anterior, con `Accept: application/xml`
- HTTP 200
- `Content-Type: application/xml; charset=utf-8`
- El cuerpo empieza con `<response><success>true</success>` y contiene `<campania>`
- XSD: `http://127.0.0.1:3010/api/v1/xsd/consulta-campanias.xsd`
- La prueba unitaria acepta ese XML y rechaza el mismo XML si `<estado>` no está en la enumeración

## POST JSON y POST XML

- Método: POST
- URL: `http://127.0.0.1:3010/api/v1/queries/campanias/buscar`
- JSON: `Content-Type: application/json`, body `{"estado":"ABIERTA","page":1,"limit":5}`
- XML: `Content-Type: application/xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<busqueda><estado>ABIERTA</estado><page>1</page><limit>5</limit></busqueda>
```

- HTTP 200 en ambos
- XML con `<estado>OTRA</estado>`: HTTP 422, código `XML_INVALIDO`

## Parámetro inválido

- URL: `.../campanias?page=0`
- HTTP 400, código `PARAMETRO_INVALIDO`
- No consulta la caché de una página válida

## Registro inexistente

- URL: `.../campanias/CAMP-NO-EXISTE`
- HTTP 404, código `NO_ENCONTRADO`
- Identificador mal formado `.../campanias/!!!`: HTTP 400

## Sin autenticación

- La misma URL de campañas, sin header Authorization
- HTTP 401, código `SIN_TOKEN`

## Token inválido, expirado y revocado

- Token `no-es-un-jwt`: 401 `TOKEN_INVALIDO`
- Token firmado con `expiresIn` negativo: 401 `TOKEN_EXPIRADO` (prueba unitaria)
- Después de `POST /api/auth/logout` con el mismo Bearer, o de `SET revoked:{jti} 1 EX <segundos>`: 401 `TOKEN_REVOCADO`
- Redis: `GET revoked:{jti}` devuelve `1` y `TTL` es mayor que cero

## Sin autorización

- Login de `ana.perez@nexum.com.mx` (colaborador)
- GET `.../queries/auditoria`
- HTTP 403, código `RBAC`
- Login de `lucia.hernandez@nexum.com.mx` (líder de Turno B)
- GET `.../queries/intervenciones?unidad_organizacional_id=UO-LOG-TURNO-A`
- HTTP 403

## Rate limit

- Con `$TOKEN` válido, repetir GET `.../queries/fuentes?limit=1` más de 60 veces en un minuto
- HTTP 429, código `LIMITE_EXCEDIDO`, header `Retry-After`
- Redis: `GET ratelimit:queries-service:USR-00003:<ventana>` es un entero mayor que 60. `TTL` de esa clave es positivo
- La prueba de integración ya obtuvo este 429

## Reportes

- GET `http://127.0.0.1:3020/api/v1/reports/campanias-por-estado` con el token de Mariana
- HTTP 200
- `categories`: `["ABIERTA","CERRADA"]`
- `series[0].data`: `[1, 3]`
- PostgreSQL: `SELECT estado, COUNT(*) FROM catalogo.campania GROUP BY estado;`
- GET `.../reports/tendencia` con el token de Lucía
- La serie "Participación suficiente" trae 1 donde el grupo llega a k y null donde no. El JSON no contiene el campo `n`
- POST `.../reports/tendencia` con `{"unidad_organizacional_id":"UO-LOG-TURNO-A"}` y el token de Lucía: 403
- GET `.../reports/resumen` con Ana: 403
- GET `.../reports/fuentes` con `Accept: application/xml`: 200 y `<category>`
- GET `.../reports/solicitudes-apoyo` con el auditor, después de insertar una solicitud en MongoDB: la serie tiene un conteo y el seudónimo no sale en el JSON

## Salud

```bash
curl -s http://127.0.0.1:3010/health
curl -s http://127.0.0.1:3020/health
```

HTTP 200 y `dependencies.postgres`, `mongo` y `redis` en `up`.

## Swagger

Abrir http://127.0.0.1:3010/api/docs y http://127.0.0.1:3020/api/docs. Authorize con el token. Try it out sobre campañas y sobre campañas por estado.

## Capturas que hay que tomar

1. `docker compose ps` con los seis contenedores en healthy.
2. Swagger de consultas, Authorize, y Try it out de GET campañas en 200.
3. La misma llamada repetida, con `meta.cache` en HIT.
4. Terminal con `GET` y `TTL` de `meta.clave_cache`.
5. La misma URL con Accept XML, mostrando `Content-Type: application/xml`.
6. El archivo `services/comun/xsd/consulta-campanias.xsd` y, si se usa un validador, el XML válido aceptado y el inválido rechazado. La prueba unitaria ya lo hace.
7. Swagger de reportes y la respuesta `[1, 3]`.
8. La página http://127.0.0.1:3001/consultas-reportes.html con la gráfica de barras ABIERTA y CERRADA.
9. Una llamada sin token, estado 401.
10. Auditoría con Ana, estado 403.
11. La ráfaga que devuelve 429.
12. `npm run test:micro` y `npm run test:integracion` en verde.
13. `GET counter:queries:consultas` y `GET counter:reports:generados`.
14. `GET revoked:{jti}` después del logout.

No hace falta capturar el JWT completo. En los logs solo aparece el prefijo del `jti`.
