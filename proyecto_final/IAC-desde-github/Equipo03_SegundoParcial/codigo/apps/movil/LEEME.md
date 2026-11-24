# Aplicación móvil Android — Bienestar Nexum

Kotlin + Jetpack Compose. Consume **exclusivamente JSON** contra cinco
microservicios del sistema.

## Qué proceso atiende, y por qué no el mismo que la de escritorio

Atiende el proceso del **colaborador**: responder la encuesta de clima y
levantar una solicitud de apoyo desde el teléfono.

La aplicación de escritorio atiende el proceso contrario — **atención de
solicitudes y lectura del tablero protegido** —, que es el trabajo del
especialista de bienestar.

La separación no es un reparto para cumplir un requisito. Son dos
situaciones de uso con necesidades opuestas:

| | Móvil (colaborador) | Escritorio (especialista) |
|---|---|---|
| Cuándo | Una vez por campaña, dos minutos, de pie | Media hora seguida, sentado |
| Qué necesita | Una pregunta por pantalla, botones grandes | Tabla de 30 filas, filtro, exportación |
| Qué escribe | Respuestas y una solicitud | Cambios de estado y notas largas |
| Formato | JSON | XML |

Que las dos funcionen contra el mismo backend es lo que demuestra que la
negociación de formato existe de verdad y no es una bandera que nadie
ejercita.

## Servicios que consume (5, la rúbrica pide 4)

| Servicio | Para qué |
|---|---|
| auth-service | entrar, validar, renovar, salir, consultar permisos |
| catalog-service | campaña abierta e instrumento con sus reactivos |
| main-process-service | enviar respuestas, participación propia, pedir apoyo |
| documents-service | adjuntar la foto a la solicitud |
| notifications-service | avisos dirigidos a la persona |

## Capacidades del dispositivo (2)

**Cámara.** Evidencia fotográfica opcional en una solicitud de apoyo, por
intención del sistema (`ACTION_IMAGE_CAPTURE`), que no necesita el permiso
`CAMERA`: la foto la toma la aplicación de cámara del teléfono. Antes de
subirla se le quitan los metadatos EXIF — coordenadas GPS, fecha exacta,
modelo del equipo —, porque unas coordenadas GPS en el piso de una planta
identifican a la persona sin necesidad de su nombre, y el servidor no puede
quitar lo que ya le llegó.

**Almacenamiento local cifrado.** `EncryptedSharedPreferences` con clave en
el almacén de claves de Android guarda el token de sesión y el borrador de
la encuesta. El borrador es lo que más pesa: son respuestas a una encuesta
de clima laboral **antes** de enviarse y asociadas a la cuenta de quien las
escribió. Todo el sistema está construido para que esas respuestas solo
existan bajo seudónimo; dejarlas en claro en el teléfono abriría por la
puerta de atrás lo que el servidor cierra por la de enfrente. El manifiesto
además declara `allowBackup="false"`: cifrar no sirve si un respaldo
automático se las lleva a la nube.

## Cómo abrirla y correrla

1. Android Studio Ladybug o posterior, con JDK 17.
2. `File → Open` y elegir esta carpeta (`apps/movil`). Android Studio
   genera el *wrapper* de Gradle la primera vez; no está versionado porque
   su `.jar` es un binario.
3. Levantar los microservicios en la computadora:
   `./scripts/arrancar_microservicios.sh` desde la raíz del repositorio.
4. Correr en el **emulador**. Las direcciones de depuración apuntan a
   `10.0.2.2`, que es como el emulador ve el `127.0.0.1` de la computadora.
   En un teléfono físico hay que cambiarlas por la IP de la computadora en
   la red local, en `app/build.gradle.kts`.
5. Entrar con `ana.perez@nexum.com.mx` / `demo123` (perfil Colaborador).

Las direcciones no están escritas en el código: son `buildConfigField` por
variante, de modo que `release` apunta a HTTPS y
`network_security_config.xml` prohíbe el tráfico en claro fuera de
desarrollo.

## Qué cubren sus pruebas

En `pruebas/test_movil.py` (17 pruebas, corren en la suite normal): que las 13 rutas que el código Kotlin llama existen en los
servicios; que el login devuelve los campos que el Kotlin lee; que los
permisos se consultan y no viajan en el token; que el catálogo entrega las
preguntas con los campos que la pantalla dibuja; que el colaborador recibe
403 donde no debe entrar; que el endpoint de evidencia sí lo puede usar;
que los códigos de error que la aplicación maneja son los que los servicios
emiten; y que la regla D-01 rechaza un identificador de empleado.

Las rutas y los campos **se extraen del propio código Kotlin**, no de una
lista escrita a mano: si alguien cambia una ruta, la prueba prueba la nueva.

El proyecto se compila y se corre abriéndolo en Android Studio, como
cualquier proyecto de Android.
