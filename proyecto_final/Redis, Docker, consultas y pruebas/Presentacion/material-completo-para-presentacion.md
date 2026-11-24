# Material completo para armar la presentación

Este texto es la fuente de verdad para generar las diapositivas. No inventes funciones, puertos, cifras ni servicios que no aparezcan aquí.

## Cómo deben quedar las diapositivas

- En español, con bullets cortos y frases pequeñas. Nada de párrafos largos.
- Presenta el sistema completo. No digas "lo que me tocó", "mi parte", "integrante 4" ni "los otros integrantes".
- No menciones carpetas, rutas de archivos, ni cómo está organizado el repositorio.
- No digas que algo "se tocó" o "se modificó". Describe lo que el sistema hace.
- No hables de aplicación Android ni de aplicación de escritorio. Esta entrega no las incluye. Sí habla de JSON y XML, porque los servicios ya responden en los dos formatos.
- No presentes 1 y 3 como cifras fijas del sistema. El reporte cuenta las campañas que haya en PostgreSQL en ese momento. Con los datos cargados ahora se ven 1 abierta y 3 cerradas. Si se agrega, abre o cierra una campaña, la gráfica cambia.
- Cuentas de demostración, todas con contraseña `demo123`:
  - mariana.solis@nexum.com.mx, especialista. Sirve para consultas y para la gráfica.
  - ana.perez@nexum.com.mx, colaboradora. Sirve para mostrar un 403 en la bitácora.
  - lucia.hernandez@nexum.com.mx, líder del Call Center Turno B. Solo ve su unidad.
  - roberto.garcia@nexum.com.mx, auditor.
  - carlos.ramirez@nexum.com.mx, administrador.

## Qué es el sistema

Bienestar Nexum es una plataforma de bienestar laboral y prevención de burnout. Las personas responden un instrumento de forma voluntaria. Las respuestas se guardan con seudónimo. Nadie puede ver un puntaje individual. Los resultados de grupo solo se publican si hay suficientes respuestas y llevan ruido de privacidad.

La web permite entrar, responder y consultar según el perfil. Además existen dos servicios:

- Consultas: búsquedas con página, filtro y orden.
- Reportes: totales y series listas para gráficas Highcharts.

Los tres se despliegan con Docker, junto con PostgreSQL, MongoDB y Redis.

## Arquitectura que hay que explicar

Seis contenedores en una red llamada `nexum`:

- Web.
- Consultas.
- Reportes.
- PostgreSQL.
- MongoDB.
- Redis.

Dentro de la red los componentes se llaman por nombre: `api`, `queries-service`, `reports-service`, `postgres`, `mongo`, `redis`. No se usa la dirección de la máquina para hablar entre ellos.

PostgreSQL guarda el negocio: campañas, unidades, instrumentos, intervenciones, bitácora y resultados protegidos. MongoDB guarda solicitudes de apoyo, que son documentos. Redis guarda lo temporal: sesión, tokens cerrados, caché, contadores y el límite de llamadas.

## Recorrido de una petición

1. La persona entra en la web. El acceso revisa la contraseña en PostgreSQL.
2. Se crea un JWT. En Redis se guarda `session:` más el identificador del token, por 15 minutos.
3. Ese token se envía a consultas o a reportes en el header `Authorization: Bearer`.
4. El servicio comprueba, en orden: que el token exista, que la firma sea válida, que no esté vencido, que no esté en `revoked:`, y que la sesión siga en Redis.
5. Después mira el perfil. Si no alcanza, responde 403.
6. Busca la respuesta en Redis. Si está, es un acierto de caché. Si no, lee PostgreSQL o MongoDB, guarda el resultado 60 segundos y responde.
7. La respuesta sale en JSON. Si el cliente pide `Accept: application/xml`, el mismo contenido sale en XML.

## Servicio de consultas

Responsabilidad: solo leer. No crea campañas, no guarda respuestas y no recalcula el ruido de privacidad.

Prefijo de las rutas: `/api/v1/queries`. Todas piden token, menos la salud, Swagger y los esquemas XSD.

Operaciones:

- Listar campañas. Filtros: texto, estado (BORRADOR, ABIERTA, CERRADA, CANCELADA), orden por secuencia, nombre o fecha. Cualquier perfil autenticado.
- Buscar campañas con el filtro en el cuerpo, en JSON o en XML.
- Ver una campaña. Si el id no existe, 404. Si el id viene mal formado, 400.
- Listar y ver unidades. Filtros: texto, tipo y si está activa.
- Listar instrumentos activos.
- Listar fuentes de datos. Unas están autorizadas (autoreporte) y otras prohibidas (correo, chat, GPS, teclado, navegación), porque serían vigilancia.
- Listar intervenciones organizacionales. El líder solo ve su unidad. Si pide otra, 403. Una intervención nunca apunta a una persona.
- Ver la bitácora: quién entró, qué consultó y con qué resultado. Solo auditor y administrador. No incluye el contenido de las respuestas.
- Buscar en la bitácora con cuerpo JSON o XML. Fechas `desde` y `hasta`. Si `desde` es posterior a `hasta`, 422.
- Ver resultados ya publicados (vista protegida). No muestra el número exacto de personas.
- Ver el presupuesto de privacidad por campaña y unidad.
- Ver solicitudes de apoyo guardadas en MongoDB. Solo auditor y administrador. El seudónimo no sale en la respuesta.
- Ver la participación propia. Solo el colaborador, y solo su fila. Sin puntaje.
- Ver el contador de consultas. Solo el administrador.

Paginación de los listados:

```json
{ "page": 1, "limit": 20, "total": 4, "totalPages": 1 }
```

`limit` va de 1 a 100. `page` empieza en 1.

## Servicio de reportes

Responsabilidad: agregar datos ya guardados y devolverlos como gráfica. No ejecuta el mecanismo de Laplace.

Prefijo: `/api/v1/reports`.

La forma de todas las gráficas es:

```json
{
  "categories": ["ABIERTA", "CERRADA"],
  "series": [{ "name": "Campañas", "data": [1, 3] }]
}
```

Operaciones:

- Resumen: conteos de campañas, unidades activas, intervenciones y resultados protegidos. El líder queda limitado a su unidad. El conteo de auditoría solo se suma para auditor y administrador.
- Campañas por estado. Cualquier perfil autenticado. Cuenta las filas de `catalogo.campania` agrupadas por estado. No hay un arreglo fijo. Con los datos cargados en este momento el conteo es 1 abierta y 3 cerradas, y cambia si cambia el catálogo.
- Intervenciones por estado. Si no hay planes, la serie queda vacía. Eso es correcto: no se inventan planes.
- Reglas de riesgo por nivel. Son reglas organizacionales, no evalúan a una persona.
- Fuentes autorizadas frente a fuentes prohibidas.
- Tendencia por campaña. Dos series: "Participación suficiente" (1 si el grupo llega al mínimo k, vacío si no) y "Valor protegido" (solo si ya fue publicado). Nunca se envía el tamaño exacto del grupo. El líder de demostración es Lucía y su unidad es Call Center Turno B. Si pide Logística, recibe 403.
- La tendencia también acepta POST con JSON o XML.
- Auditoría por tipo de acción y auditoría por día. Solo auditor y administrador.
- Distribución de estados de publicación. Lee filas ya guardadas. Si todavía no hay publicación, la serie va vacía y el mensaje lo dice.
- Solicitudes de apoyo agrupadas por estado, desde MongoDB. Sin seudónimo.
- Contador de reportes generados. Solo administrador.

k, el mínimo para publicar un grupo, está en la base. En la demostración vale 5. Turno B supera ese mínimo. Logística no. Por eso un punto vacío significa "grupo insuficiente", no un cero de bienestar.

## Por qué el reporte no recalcula el algoritmo

El flujo de privacidad es: respuestas, recorte al rango de la escala, comprobar que el grupo llega a k, promedio, sensibilidad, ruido de Laplace, publicación. Eso ya está en la base y cada consulta protegida consume un presupuesto llamado épsilon. Cuando el presupuesto se acaba, el sistema deja de publicar. El reporte no dispara ese cálculo. Lee lo publicado. Así una gráfica no agota la privacidad de una unidad.

## Redis, implementación

Un solo Redis para todo el sistema. Los servicios lo usan en `redis:6379`.

Claves y tiempos:

- `session:{jti}`. Sesión del token. Se crea al entrar. TTL de 15 minutos, igual a la vida del JWT. Si no existe, el servicio responde 401.
- `revoked:{jti}`. Token cerrado antes de tiempo. Se crea al salir. TTL igual a los segundos que le quedaban al token. Si existe, el servicio responde 401.
- `contador:login_fallido:{usuario}`. Intentos fallidos de acceso. TTL 15 minutos.
- `cache:agregado:{unidad}:{campania}`. Resultado protegido que ya calculó el proceso de agregados. TTL 5 minutos.
- `lock:calculo_agregado:{unidad}`. Candado del cálculo que gasta privacidad. TTL 10 segundos. Evita que dos cálculos simultáneos se pasen del presupuesto.
- `cache:queries-service:{recurso}:{hash}` y `cache:reports-service:{recurso}:{hash}`. Respuesta de una lectura. TTL 60 segundos, configurable. El hash incluye los filtros y el perfil, para que el líder no reciba la caché de otro perfil.
- `lock:cache:{servicio}:{recurso}:{hash}`. Candado de 10 segundos. Si varias peticiones iguales llegan juntas y la caché está vacía, solo una lee la base. Las otras esperan y luego encuentran el acierto.
- `ratelimit:{servicio}:{usuario}:{ventana}`. Cuenta de llamadas en esa ventana. TTL 60 segundos. Tope 60 llamadas. Al pasarse: HTTP 429 y header `Retry-After`. Si Redis no responde, el límite no se apaga: el servicio responde 503.
- `counter:queries:consultas` y `counter:reports:generados`. Totales. No caducan, porque no son datos temporales.
- `counter:queries:consultas:{fecha}` y `counter:reports:generados:{fecha}`. Conteo del día. Caducan a las 48 horas.
- `cache:auth:contexto:{usuario}`. Unidad del usuario, para no preguntarla en cada petición. TTL 60 segundos. No guarda el seudónimo.

En los logs, la primera lectura dice exactamente `CACHE MISS` y la repetición dice `CACHE HIT`. La respuesta también lo trae en `meta.cache`, y la clave exacta en `meta.clave_cache`.

Si Redis no está disponible al validar el token, no se deja pasar "por si acaso". La respuesta es 503.

Comandos para la demostración, dentro de Redis:

- `GET` de la clave que devolvió `meta.clave_cache`.
- `TTL` de esa clave. Un número positivo son los segundos restantes. `-1` significa que existe y no caduca (es el caso de los contadores totales).
- `GET counter:queries:consultas`
- `GET counter:reports:generados`
- `GET revoked:{jti}` después de cerrar sesión. Debe valer `1`.

No se recorre Redis con `KEYS` en el código del sistema. En la demostración se consulta la clave concreta.

## Docker, implementación

Cada programa va en su imagen. La web usa una imagen de Node. Consultas y reportes usan `node:22`, instalación con el lock de dependencias, y el proceso corre con un usuario sin privilegios de administrador. No se copian contraseñas dentro de la imagen. Las variables llegan al arrancar.

Compose hace esto:

- Crea la red `nexum`.
- Levanta PostgreSQL 15. Base `bienestar_nexum`. Usuario de demostración `postgres`. La primera vez carga el esquema y los datos de prueba. Los datos persisten en el volumen `pgdata`.
- Levanta MongoDB 7. Base `bienestar_nexum`. Volumen `mongodata`. Hay un índice por fecha en las solicitudes de apoyo.
- Levanta Redis 7 con persistencia AOF. Volumen `redisdata`.
- Levanta la web, consultas y reportes solo cuando las tres bases pasan su revisión de salud.
- Consultas y reportes tienen su propia revisión: `GET /health`. Si la app, PostgreSQL, MongoDB o Redis fallan, el estado no es sano.

Variables que cambian el comportamiento, sin reconstruir la lógica:

- Secreto del JWT, compartido por la web y los dos servicios.
- Algoritmo, por defecto HS256. Si más adelante hubiera llave pública, se puede pasar a RS256.
- Emisor y audiencia del token: solo se exigen si tienen valor. El token actual no los trae.
- Vida de la caché, tope de llamadas y ventana del límite.
- Orígenes permitidos para que la web llame a consultas y reportes.

Comandos:

- `docker compose up -d` enciende todo.
- `docker compose ps` muestra el estado. En la demostración los seis deben verse sanos.
- `docker compose logs` seguido del nombre del servicio muestra `CACHE HIT`, `CACHE MISS` y los rechazos.
- `docker compose down` apaga. Borrar también los volúmenes borra las bases. No hace falta para una demo normal.

## Puertos

Dentro de su contenedor, la web, las consultas y los reportes escuchan en el 3000. No chocan porque cada uno tiene su contenedor.

Hacia afuera:

| Servicio | Dentro de la red | Hacia afuera | Motivo |
| --- | --- | --- | --- |
| Web | 3000 | 3001 | Puerto publicado de la aplicación |
| Consultas | 3000 | 3010 | Puerto propio, seguido de la web |
| Reportes | 3000 | 3020 | Puerto propio |
| PostgreSQL | 5432 | 5433 | 5432 es el puerto habitual de Postgres |
| MongoDB | 27017 | 27017 | Puerto habitual de Mongo |
| Redis | 6379 | 6379 | Puerto habitual de Redis |

Direcciones de la demostración:

- Web: puerto 3001.
- Gráfica: puerto 3001, página de consultas y reportes. Al entrar como Mariana dibuja las barras de campañas.
- Swagger de consultas: puerto 3010, ruta `/api/docs`.
- Swagger de reportes: puerto 3020, ruta `/api/docs`.
- Salud: puerto 3010 y puerto 3020, ruta `/health`. Deben decir PostgreSQL, MongoDB y Redis en `up`.

## Seguridad

Un solo mecanismo de token.

El JWT trae:

- `sub`: identificador del usuario, por ejemplo `USR-00003`.
- `perfil`: COLABORADOR, LIDER, ESPECIALISTA, AUDITOR o ADMINISTRADOR.
- `jti`: identificador único de esa sesión.

Firma HS256 con el secreto compartido. El servicio rechaza otro algoritmo.

Casos que hay que poder mostrar:

- Sin header Authorization: 401, código `SIN_TOKEN`.
- Token que no es un JWT: 401, `TOKEN_INVALIDO`.
- Token vencido: 401, `TOKEN_EXPIRADO`.
- Token de una sesión cerrada: 401, `TOKEN_REVOCADO`.
- Sesión que ya no está en Redis: 401, `SESION_INVALIDA`.
- Colaboradora pidiendo la bitácora: 403, `RBAC`.
- Líder pidiendo la unidad de otro equipo: 403.

El líder de la demostración solo alcanza Call Center Turno B (`UO-CC-TURNO-B`).

Los logs registran el usuario, el perfil y solo los primeros caracteres del identificador del token. No registran la contraseña ni el token completo.

Las lecturas de PostgreSQL van con parámetros. El texto de búsqueda no se pega dentro de la sentencia. El orden solo acepta columnas de una lista cerrada.

## JSON, XML y XSD

Éxito:

```json
{
  "success": true,
  "message": "Campañas consultadas",
  "data": {},
  "pagination": { "page": 1, "limit": 20, "total": 1, "totalPages": 1 },
  "meta": { "cache": "MISS", "servicio": "queries-service", "clave_cache": "cache:queries-service:campanias:..." }
}
```

Error:

```json
{
  "success": false,
  "error": { "code": "NO_ENCONTRADO", "message": "La campaña no existe", "details": {} }
}
```

`/health` no usa ese sobre. Responde `status` y `dependencies`, para que Docker solo mire si el código HTTP es correcto.

XML: mismo contenido, raíz `<response>`. Las listas se vuelven elementos repetidos (`campania`, `category`, `point`). Un punto vacío significa nulo en la gráfica.

Entrada XML, validada contra esquema antes de usarse:

- Búsqueda de campañas. Estado solo puede ser BORRADOR, ABIERTA, CERRADA o CANCELADA. Página mínima 1. Límite entre 1 y 100.
- Búsqueda de auditoría.
- Filtro de tendencia: unidad, dimensión y fechas.

Un XML ilegible responde 400. Un XML bien formado que no cumple el esquema responde 422, código `XML_INVALIDO`.

Esquemas publicados: respuesta de campañas, error, búsqueda de campañas, búsqueda de auditoría, petición de tendencia y gráfica Highcharts. Se consultan en `/api/v1/xsd/` más el nombre del esquema. La prueba automática acepta un XML válido y rechaza uno cuyo estado no está en la lista.

## Swagger

Cada servicio tiene su documentación OpenAPI ejecutable.

Incluye descripción, método, ruta versionada, parámetros, header Accept, token Bearer, ejemplo JSON, ejemplo XML y los códigos 200, 400, 401, 403, 404, 422, 429, 500 y 503.

En la demo: Authorize, pegar el token, Try it out sobre campañas y sobre campañas por estado.

## MongoDB, qué se demuestra desde estos servicios

La colección es `solicitudes_apoyo`. Cada documento tiene mensaje, estado, fecha y un seudónimo que no se devuelve.

Estos servicios hacen:

- Consulta filtrada y paginada.
- Agregación por estado para la gráfica.
- Índice por fecha.

La inserción de una solicitud de apoyo la hace la propia persona desde la web. Estos servicios no la crean. Si no hay documentos, la gráfica queda vacía y el mensaje lo dice.

## Qué se puede demostrar de punta a punta

1. `docker compose ps` con los seis contenedores sanos.
2. Salud de consultas y de reportes.
3. Entrar como Mariana y obtener el token.
4. En Swagger, listar campañas abiertas. Primera vez: caché en fallo. Log: `CACHE MISS`.
5. Repetir. Caché en acierto. Log: `CACHE HIT`.
6. En Redis, `GET` y `TTL` de `meta.clave_cache`.
7. La misma consulta con `Accept: application/xml`. El tipo de contenido es `application/xml`.
8. Mostrar que un estado inválido en el XML se rechaza.
9. Reporte de campañas por estado: las categorías son los estados que existan en la base y los números son el conteo de ese momento. Con los datos cargados se ve ABIERTA 1 y CERRADA 3. Si se inserta otra campaña, la barra cambia.
10. Abrir la página de consultas y reportes, entrar como Mariana, y mostrar las dos barras.
11. Sin token: 401. Colaboradora en bitácora: 403. Campaña inexistente: 404. Página 0: 400.
12. Más de 60 llamadas en un minuto: 429.
13. Cerrar sesión y reutilizar el token: 401 por token revocado. En Redis, `revoked:{jti}` vale 1.
14. Contadores de consultas y de reportes.
15. Pruebas: 13 del sistema, 16 de consultas, reportes, Redis y XML, y 3 de integración con los contenedores. Esas 3 cruzan token, Redis, el servicio y la base, e incluyen JSON, XML, acierto de caché y el 429.

## Resultados ya comprobados

- Los seis contenedores llegaron a estado sano.
- Un token emitido por el inicio de sesión real abrió consultas y reportes.
- La campaña abierta de demostración es `CAMP-2026-S4`, Medición semana 4.
- El reporte de campañas por estado, consultando la base en ese momento, devolvió 1 abierta y 3 cerradas. No es un valor escrito en el servicio.
- La página dibujó esa gráfica con Highcharts.
- Desde el servicio de consultas se alcanzó el servicio de reportes por su nombre interno, y la salud respondió 200.
- La integración automática pasó los casos de éxito, parámetro inválido, registro inexistente, 401, 403, 404, 422, 429, XML, fallo de caché y acierto de caché.

## Qué no debe afirmar la presentación

- No digas que existe una aplicación móvil ni una de escritorio.
- No digas que hay contenedores separados de autenticación, usuarios, catálogos, documentos o notificaciones. El acceso y la web están en el servicio web. Consultas y reportes son los servicios adicionales en marcha.
- No digas que la tendencia siempre trae un valor protegido numérico. Ese valor aparece cuando el proceso de agregados ya lo publicó. Si no hay filas, el punto va vacío y el texto lo explica.
- No digas que se recorren todas las claves de Redis en el sistema. Se consulta la clave concreta.
- No inventes otro esquema de sesión. La sesión es `session:{jti}` y la revocación es `revoked:{jti}`.

## Guion corto, en el orden de las láminas

1. El sistema es de bienestar laboral. Los resultados son de grupo, nunca de una persona.
2. Hay web, consultas y reportes, más PostgreSQL, MongoDB y Redis.
3. Consultas buscan. Reportes grafican. Los dos solo leen.
4. El reporte no recalcula el ruido, para no gastar el presupuesto de privacidad.
5. El token se valida contra Redis antes de responder.
6. Redis guarda sesión, revocación, caché de 60 segundos, contadores y el límite de 60 llamadas.
7. La primera lectura es un fallo de caché. La segunda es un acierto. El TTL se ve en Redis.
8. Docker levanta los seis contenedores en la red `nexum`.
9. Puertos publicados: web 3001, consultas 3010, reportes 3020, Postgres 5433, Mongo 27017, Redis 6379.
10. Swagger ejecuta la petición. JSON o XML, el mismo dato.
11. La gráfica de campañas muestra 1 y 3.
12. 401, 403, 404, 400 y 429 son respuestas controladas.
13. Las pruebas de integración cruzan token, Redis, servicio y base.
14. Cierre: un despliegue, un token, una memoria compartida y dos servicios de lectura sobre los datos reales.
