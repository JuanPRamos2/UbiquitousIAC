# Cómo funcionan los cambios

El sistema de siempre sigue siendo la web de Bienestar Nexum. Lo nuevo son dos servicios que solo leen, más el uso compartido de Redis y el arranque de todo en Docker.

## El recorrido de una petición

1. La persona entra en la web (`api`, puerto 3001 en este equipo).
2. El login del monolito revisa la contraseña en PostgreSQL y guarda la sesión en Redis con la clave `session:{jti}`. Devuelve un JWT.
3. La web, Swagger o un `curl` mandan ese token a consultas (puerto 3010) o a reportes (puerto 3020).
4. El servicio comprueba, en este orden: que el token venga, que la firma sea válida, que no esté expirado, que no esté en `revoked:{jti}` y que la sesión siga en Redis. Después mira el perfil.
5. Si la misma consulta se hizo hace menos de 60 segundos, Redis responde y el log dice `CACHE HIT`. Si no, el log dice `CACHE MISS`, se lee PostgreSQL o MongoDB, se guarda el resultado en Redis con vencimiento y se responde.
6. La respuesta sale en JSON. Si el cliente pide `Accept: application/xml`, el mismo contenido sale en XML.

Consultas y reportes no crean campañas, no guardan respuestas y no vuelven a calcular el ruido de privacidad. Ese cálculo sigue en el monolito.

## Qué hace cada pieza y dónde se ve

| Pieza | Qué hace | Dónde está el código | Dónde se ve funcionando |
| --- | --- | --- | --- |
| Web | Login y la gráfica de campañas | `web/` y `web/consultas-reportes.html` | http://127.0.0.1:3001 y http://127.0.0.1:3001/consultas-reportes.html |
| Consultas | Lista campañas, unidades, bitácora, intervenciones y lo demás, con filtros y páginas | `services/queries-service/` | http://127.0.0.1:3010/api/docs |
| Reportes | Arma series para gráficas contando lo que haya en PostgreSQL. Campañas por estado cambia si cambia el catálogo | `services/reports-service/` | http://127.0.0.1:3020/api/docs |
| Común | JWT, caché, XML, XSD, errores y nombres de claves de Redis. Lo usan los dos servicios | `services/comun/` | No tiene pantalla. Se nota en el 401, el 403, el XML y el `CACHE HIT` |
| Redis | Sesión, token revocado, caché, contadores y límite de peticiones | Contenedor `redis`. Claves descritas en `services/comun/src/claves-redis.js` | `docker compose exec redis redis-cli` |
| PostgreSQL | Campañas, unidades, bitácora y vistas protegidas | Contenedor `postgres`, base `bienestar_nexum` | Los JSON de consultas y reportes |
| MongoDB | Solicitudes de apoyo | Contenedor `mongo`, colección `solicitudes_apoyo` | `GET /api/v1/queries/solicitudes-apoyo` con el auditor |
| Docker | Un contenedor por pieza, en la red `nexum` | `docker-compose.yml` y los `Dockerfile` | `docker compose ps` |

## Qué se cambió en lo que ya existía

| Archivo | Cambio |
| --- | --- |
| `docker-compose.yml` | Se agregaron consultas, reportes y la red `nexum`. La web, PostgreSQL, MongoDB y Redis siguen. |
| `.env.example` | Variables de JWT, caché, rate limit y puertos. |
| `src/app.js` | La web puede llamar a los puertos 3010 y 3020. |
| `web/index.html` | Enlace «Consultas y reportes». |
| `src/utilidades/redis-claves.js` | Un comentario que apunta a la lista común de claves. Las claves viejas no se renombraron. |
| `README.md` y `docs/arquitectura.md` | Un enlace a esta carpeta. |
| `package.json` | Comandos `npm run test:micro` y `npm run test:integracion`. |

## Cómo comprobarlo en cuatro pasos

```bash
cd ~/Documents/UbiquitousIAC/proyecto_final
docker compose ps
```

1. Salud: `curl http://127.0.0.1:3010/health` y `curl http://127.0.0.1:3020/health`. PostgreSQL, MongoDB y Redis deben decir `up`.
2. Login y consulta. Entra como `mariana.solis@nexum.com.mx` / `demo123` y abre el Swagger de consultas, o usa el token en:

```bash
curl -H "Authorization: Bearer EL_TOKEN" \
  "http://127.0.0.1:3010/api/v1/queries/campanias?estado=ABIERTA&limit=2"
```

La primera vez `meta.cache` es `MISS`. La segunda, `HIT`.

3. Reporte y gráfica. El mismo token en `http://127.0.0.1:3020/api/v1/reports/campanias-por-estado` devuelve ABIERTA y CERRADA. La página `consultas-reportes.html` dibuja esas barras.
4. XML. La misma consulta de campañas con el header `Accept: application/xml`.
