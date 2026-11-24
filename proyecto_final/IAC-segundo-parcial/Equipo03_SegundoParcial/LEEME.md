# Segundo parcial integrado — Equipo 03

La base es la corrección de Emiliano y Gerardo. Encima están los servicios
de Juan Pablo y Ricardo para completar los 24 microservicios.

Proyecto 4. Plataforma de Bienestar Laboral y Prevención de Burnout
Integración de Aplicaciones Computacionales · UDEM · Equipo 03

| | |
|---|---|
| Emiliano Pascual Piñales Sánchez | #657657 |
| Gerardo Quiroga Ramírez | #650313 |
| Ricardo Arath Sánchez Aguirre | #583928 |
| Juan Pablo Ramos Salazar | #610248 |

Este paquete ya no es solo la parte de Emiliano y Gerardo. Esa corrección
está integrada, y encima están los ocho servicios que faltaban para el
reparto de 24 (puertos 8110, 8111, 8112, 8113, 8116, 8117, 8118 y 8119):

| Integrante | Servicios nuevos |
|---|---|
| Juan Pablo #610248 | consent 8110, privacy 8111, audit 8118, data-governance 8119 |
| Ricardo #583928 | survey 8112, indicators 8113, support 8116, organizational 8117 |

auth, users, catalog y main-process siguen. El ruido de Laplace no se
recalcula en privacy-service: sigue en `agregado.fn_ruido_laplace`.

---

## Lo que señaló la revisión, y qué se hizo con cada cosa

**«Hacen una entrega que pareciera que ni siquiera se tomaron la molestia
de revisar.»** Era cierto y se puede señalar dónde. Los documentos decían
«nueve microservicios» cuando ya había más, «las seis migraciones» cuando
ya había diez, y un conteo de pruebas viejo. El paquete anterior se fue
con `dump.rdb`, `.pytest_cache` y los `__pycache__` dentro.

Ahora esas cifras **se leen del repositorio** al generar los documentos
(`docs/actualizar_documentos.py`), y hay una prueba —
`pruebas/test_documentos.py`, 24 casos — que falla si un documento vuelve
a contradecir al código. El paquete lo arma `scripts/armar_entrega.sh`,
que se niega a terminar si encuentra basura.

**«Dicen muchas cosas que no tienen sentido.»** Se quitó la sección de
limitaciones que hablaba del entorno en lugar del sistema, y se
reescribieron las afirmaciones que daban por hecho trabajo no comprobado.
Lo que no se pudo verificar se dejó de afirmar, en los dos sentidos: ya no
se afirma que algo funcione ni que algo falle sin haberlo corrido.

**«Cada integrante debe entender y responder por sus microservicios.»** El
reparto está en la tabla de abajo, y cada `app.py` empieza con las
decisiones de diseño de ese servicio y su consecuencia. Donde el documento
decía «Consultas» o «Reportes» sin nombre, ahora hay un nombre.

**«Eliminar funcionalidad innecesaria.»** Lo que se quitó está en la
sección 9.3 del manual, con el motivo de cada cosa. Lo más grande: el
manejo de archivos de evidencia vivía en el portal web —validaba firmas,
calculaba hashes y escribía en el almacén— y se movió a
`documents-service`, que es el responsable del recurso.

**«Probar realmente cada componente.»** 499 pruebas, de las que **425
pasan sin nada más levantado**; corrimos la suite dos veces seguidas y da
el mismo resultado. Las 47 restantes necesitan `npm install`, los
servicios levantados o el proyecto Android compilado, y casi todas se
saltan solas en lugar de fallar. El desglose exacto está en el
`README.md`, no escondido.

Las pruebas no se escribieron para confirmar que el código funciona: se
escribieron para intentar romperlo, y encontraron quince defectos reales que
están listados más abajo. Dos de ellos eran de los que no se notan —el
servicio contestaba que todo salió bien y no había guardado nada.

---

## El reparto

| Integrante | Microservicios | Puertos |
|---|---|---|
| **Emiliano** #657657 | queries, reports, algorithms, trends, interventions, export | 8107, 8108, 8109, 8114, 8115, 8121 |
| **Gerardo** #650313 | documents, notifications, sync, configuration, monitoring, integration | 8105, 8106, 8120, 8122, 8123, 8124 |

Los de los integrantes 1 y 2 (auth, users, catalog, main-process) siguen
como estaban.

---

## Los defectos que encontraron las pruebas

Ninguno salió de leer el código: todos los destapó una prueba escrita
contra el componente. Se listan con su consecuencia, porque un defecto sin
consecuencia escrita no se distingue de una preferencia de estilo.

| Dónde | Qué estaba mal | Qué habría pasado |
|---|---|---|
| `sync-service` | La respuesta se registraba con una consulta sin `COMMIT` | Contestaba `APLICADA` sin guardar nada: el cliente borraba su copia local de una respuesta que nunca se escribió |
| `integration-service` | El filtro de campos de persona coincidía por contenido, y «nombre» coincide con `nombre_unidad` | Rechazaba todo archivo de estructura bien formado |
| `integration-service` | La lista de tipos de unidad estaba escrita a mano y había quedado distinta de la restricción de la base | Validaba el archivo, lo declaraba correcto y reventaba al insertar |
| `integration-service` | Consultaba `consentimiento.seudonimo`, que el rol de la aplicación no puede leer | Fallaba con «permission denied», que es la garantía del proyecto funcionando |
| `interventions-service` | Leía el `RETURNING` por posición y el cursor devuelve diccionarios | Error 500 al crear cualquier plan |
| `interventions-service` | No contemplaba la restricción de una evaluación por plan | 500 con el error de PostgreSQL asomando en la respuesta |
| `fn_validar_arbol_propuesto` | Una unidad que era su propio padre daba dos hallazgos de ciclo | Un informe que repite hallazgos hace dudar de la cuenta de errores |
| Las pruebas propias | Tomaban siempre el mismo seudónimo y leían tablas prohibidas al rol | Pasaban solas y fallaban al correr la suite dos veces |
| Los dos compose | No montaban las migraciones nuevas | Una base creada con ellos levanta y falla al primer uso real |
| `arrancar_microservicios.sh` | Su lista se había quedado corta | El manual manda correr ese guión y no levantaba los servicios nuevos |
| `monitoring-service` | `cursor` no estaba importado, y el `try` del registro se tragaba el `NameError` | La supervisión de reinicios funcionaba en pantalla y no guardaba nada. Es el modo de falla de la migración 007 otra vez: el registro va envuelto en un `try` para no tumbar la petición, así que su fallo no se ve. El `logger.error` original tampoco mostraba el motivo; ahora es `logger.exception` |
| `integration-service` | El renglón #24 pide «validación XSD» y el servicio aceptaba XML sin validarlo contra ningún esquema | Un archivo del sistema corporativo con elementos no previstos entraba hasta el código que interpreta renglones. Ahora hay `integracion.xsd`, se valida antes de leer, y el esquema se publica para validar antes de mandar |
| `queries-service` | El renglón #07 pide «por campaña, periodo y unidad» y la serie de tendencia no se podía acotar | Se agregaron `desde_campania` y `hasta_campania`. El rango entra en la clave de caché: sin eso, la primera consulta dejaba guardada la serie completa y la siguiente, acotada, recibía esa misma serie entera desde la caché — el filtro parecería no funcionar |
| `monitoring-service` | Alertas y supervisión de contenedores (esto iba **de más**: el renglón #23 pide salud, latencia y estado de BD, no esto) | Ver abajo |
| `interventions-service` | Registraba el cambio de estado y el avance con `INTERVENCION_SEGUIMIENTO`, que es un **permiso** y no una acción de bitácora | Ni un cambio de estado ni un avance quedaban registrados. El ciclo de aprobación está declarado para poder auditarlo, así que sin rastro la máquina de estados solo impide saltos y no deja constancia. Migración 015, con dos acciones separadas: mover un plan y reportar un avance son hechos distintos |
| La prueba que debía atrapar lo anterior | Buscaba el código en el texto de las migraciones, y la cadena sí aparecía ahí — como permiso | Daba por bueno un código que `auditoria.tipo_accion` no tenía. Ahora comprueba contra los `INSERT` a esa tabla |

---

## Lo que se agregó

Seis microservicios, con sus migraciones y sus pruebas:

| Servicio | Puerto | De quién | Qué resuelve |
|---|---|---|---|
| `trends-service` | 8114 | Emiliano | Si un cambio entre campañas es real o cabe dentro del ruido de Laplace |
| `interventions-service` | 8115 | Emiliano | Planes **organizacionales**, su ciclo de aprobación y su evaluación |
| `export-service` | 8121 | Emiliano | Egreso controlado de agregados, con control de fuga antes de escribir |
| `sync-service` | 8120 | Gerardo | Que reenviar un lote con red intermitente sea inofensivo |
| `configuration-service` | 8122 | Gerardo | Umbrales k, límites de consulta y presupuestos de privacidad |
| `monitoring-service` | 8123 | Gerardo | Salud, latencia, errores, **alertas** y **supervisión de reinicios** de los demás |
| `integration-service` | 8124 | Gerardo | La puerta hacia el sistema corporativo, con validación XSD |

### Dos de ellos deciden al contrario, y conviene saber por qué

`sync-service` aplica un lote **a medias**, renglón por renglón.
`integration-service` es **todo o nada**. Parece una incoherencia y no lo
es: cuarenta autoreportes con uno mal formado, aplicados a medias, son
treinta y nueve respuestas guardadas —un resultado útil, y el cliente que
las capturó sin red no tiene cómo recuperarlas si se rechazan en bloque—.
Un árbol organizacional a medio aplicar son unidades huérfanas, y el
alcance de todos los perfiles se calcula recorriendo ese árbol.

### Las dos funcionalidades que le faltaban a `monitoring-service`

Salieron al cotejar la tabla del profesor renglón por renglón, no antes.

**Supervisión de contenedores** (`GET /monitoreo/contenedores`). Un
contenedor en bucle de reinicio **pasa todas las sondas de salud**: cada
sonda le llega a un proceso recién arrancado que contesta «vivo» con toda
honestidad, así que el panel lo muestra en verde mientras el servicio
pierde cada petición en vuelo y cada conexión del pool.

Se detecta comparando la `instancia` que cada servicio reporta ahora en
`/health/live` —un identificador nuevo por proceso, que se agregó a la
biblioteca común y por tanto a los veinticuatro—. Un identificador distinto
significa un proceso nuevo.

No se lee el socket de Docker, y es una decisión, no una limitación:
montar `/var/run/docker.sock` dentro de un contenedor le da control del
demonio, y con eso puede arrancar otro contenedor con el sistema de
archivos del anfitrión montado. Equivale a root en la máquina. Además el
proyecto tiene que funcionar sin Docker, que es como corre la demostración
cuando no hay acceso a Docker Hub.

**Alertas** (`GET /monitoreo/alertas`). Ocho reglas evaluadas sobre el
estado de ahora, cada alerta con severidad, evidencia y qué hacer. La más
propia de este sistema es `PRESUPUESTO_AGOTADO`: cuando el épsilon de una
campaña se agota, la unidad deja de poder publicar; todo responde, nada
falla, y para quien opera se ve como «ya no salen datos nuevos». Sin la
alerta se busca el problema en el lugar equivocado.

El servicio **publica** las alertas, no las envía. Enviarlas exigiría
credenciales de correo y una cola de reintentos dentro de ese contenedor,
y un monitor cuyo envío falla en silencio es peor que no tener monitor:
nadie se enteraría y todos creerían estar cubiertos. La entrega de
mensajes ya la hace `notifications-service`.

### La validación XSD de `integration-service`

El renglón #24 de la tabla pide «validación XSD» y el servicio aceptaba
XML sin validarlo contra ningún esquema. Ahora hay
`contratos/xml/integracion.xsd`, se valida **antes** de leer el contenido,
y el esquema se publica en `GET /api/v1/integracion/esquema.xsd` para que
el equipo del sistema corporativo valide antes de mandar.

Conviene entender por qué hay **dos** defensas y ninguna sobra. La lista
de campos de persona del servicio es una enumeración, y una enumeración
siempre deja fuera lo que no previó: un `nss_trabajador` que a nadie se le
ocurrió anotar pasaría. El esquema invierte la carga — declara lo
permitido, con los renglones en `xs:all` cerrado — así que rechaza lo no
anticipado. Pero el esquema solo actúa sobre XML y su mensaje es «este
elemento no se esperaba», que no le dice al equipo corporativo qué quitar;
la lista cubre el JSON y **nombra** el campo culpable. Hay una prueba que
manda justamente un campo fuera de la lista negra y comprueba que el
esquema lo detiene.

La respuesta trae `validacion_xsd` con tres valores distintos:
`VALIDADO`, `NO_APLICA` (el cuerpo venía en JSON) y `NO_DISPONIBLE` (el
esquema no se pudo cargar). Anunciar «validado contra XSD» sin haber
validado sería peor que decir que no se pudo.

Lo que el esquema **no** puede comprobar es que la plantilla de un padre
sea la suma de sus hijas: eso no se expresa en XSD y lo hace
`integracion.fn_validar_arbol_propuesto` en la base. Está dicho en el
contrato para que nadie suponga que pasar el esquema significa que el
árbol cuadra.

### Dos garantías nuevas

`gobernanza.fn_verificar_garantias()` pasó de seis a ocho. Las migraciones
011 y 012 abrieron dos vías de entrada y durante un rato ninguna garantía
las miraba:

- **G7** — ninguna tabla del esquema `integracion` tiene dónde guardar un
  nombre, un correo, un RFC, un sueldo o una fecha de nacimiento.
- **G8** — ninguna tabla del esquema `sincronizacion` contiene
  `empleado_id`.

La diferencia con el filtro del servicio importa: el filtro protege de lo
que **entra**; la garantía comprueba que no haya **dónde ponerlo**, y es la
que sigue valiendo el día que alguien agregue una columna «para depurar».

```sql
SELECT * FROM gobernanza.fn_verificar_garantias();
-- Ocho renglones, los ocho en true.
```

---

## Cómo correrlo

```bash
cd codigo

# Todo con Docker
./scripts/ambiente.sh developer arriba

# O sin Docker: base, luego los veinticuatro servicios, luego el portal
./scripts/arranque_base.sh
./scripts/arrancar_microservicios.sh
./scripts/arrancar_web.sh

# Las pruebas que no necesitan nada levantado
python3 -m pytest pruebas/ -q \
  --ignore=pruebas/test_servicios_node.py \
  --ignore=pruebas/test_degradacion_web.py \
  --ignore=pruebas/test_movil.py
```

El portal queda en <http://localhost:8000> y cada servicio publica su
Swagger en `/docs` (de `:8101` a `:8124`).

---

## Qué hay en el paquete

```
documentos/     los .docx y los .pdf, con la sección de correcciones
codigo/         el monorepo
  apps/microservicios/   los veinticuatro servicios
  apps/web/              el portal
  apps/escritorio/       Tkinter, consume solo XML
  apps/movil/            Android (Kotlin + Compose), consume solo JSON
  db/migraciones/        diecisiete migraciones; de la 011 a la 017 son nuevas
  pruebas/               499 pruebas
  docs/                  los documentos y su generador
  scripts/               arranque, pruebas y armado de la entrega
```

---

## Lo que no está hecho, dicho aquí y no escondido

- Nunca se desplegó en GCP ni se corrió la integración continua en GitHub:
  los archivos de la tubería están escritos y no se han ejecutado allá.
- El proyecto Android no se pudo compilar en el entorno de trabajo porque
  Maven Central y `dl.google.com` no son alcanzables desde ahí. El código
  está completo y validado contra el contrato, pero no hay un APK.
- MongoDB no está instalado en el entorno de pruebas; las pruebas que lo
  usan corren contra `mongomock`. Los tres servicios que lo tocan lo
  declaran **opcional** a propósito, y con MongoDB caído se reportan
  `degradado` y siguen atendiendo.
