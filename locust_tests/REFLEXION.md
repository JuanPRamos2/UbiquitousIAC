# Reflexión

Las cifras de esta página salen de los CSV de `evidencias/`. Si un perfil no se corrió, se dice y no se sustituye por un número.

## 1. Monolito y microservicios

No hay CSV de load. No se afirma qué arquitectura fue más rápida.

La comparación usable es entre lecturas parecidas: el catálogo público `books GET /books?format=json` y, si hubo sesión, `monolito GET /library/books`. La salud del monolito y la de un microservicio solo dicen que el proceso respondió. Users, pedidos y pagos no tienen lectura pública; sin `LOCUST_EMAIL` y `LOCUST_PASSWORD` esas listas no entran en la prueba. Los seis procesos comparten la misma instancia y la misma rampa, así que un servicio lento compite por CPU con los demás.

## 2. Primera degradación

No hay CSV. No se puede decir qué servicio se degradó primero.

No hay `breakpoint_stats_history.csv`. El punto de quiebre no se estimó.

## 3. Diferencia entre perfiles

Smoke comprueba el guion con 1 usuario y 30 segundos. Load sostiene 5 usuarios dos minutos. Stress sube de 2 a 20. Spike salta a 15 y vuelve a 2. Soak deja 3 usuarios cuatro minutos para ver deriva. El punto de quiebre sube de uno en uno y se detiene al cruzar el umbral.

smoke: no hay CSV agregado, así que no hay p95 ni RPS de ese perfil. load: no hay CSV agregado, así que no hay p95 ni RPS de ese perfil. stress: no hay CSV agregado, así que no hay p95 ni RPS de ese perfil. spike: no hay CSV agregado, así que no hay p95 ni RPS de ese perfil. soak: no hay CSV agregado, así que no hay p95 ni RPS de ese perfil. breakpoint: no hay CSV agregado, así que no hay p95 ni RPS de ese perfil.

No hay suficiente historia del soak para comparar el tramo inicial con el final.

## 4. Limitaciones

La carga sale de una sola máquina, con pausa de 1 a 2 segundos, así que el RPS no es la capacidad máxima. El tope de cada perfil es de minutos: el soak no prueba fugas largas y el quiebre no es el límite de un despliegue con varias réplicas. Flask arranca con `app.run` sin hilos de producción; Node atiende por el bucle de eventos. La red hasta la IP pública suma latencia que no existe en un curl local. Las escrituras se evitaron, así que no hay evidencia de altas, pagos ni stock. Si un puerto no respondió en `smoke_manual.txt`, ese destino no debe leerse como un éxito.

## 5. Qué aportó la IA y qué hubo que corregir

La IA propuso un solo `locustfile` con `LoadTestShape` y un `name` distinto por destino, para no mezclar en una fila el monolito y los microservicios. También sirvió para separar usuarios, `spawn_rate`, `wait_time` y duración: el spawn solo describe la rampa, y la espera entre tareas no es latencia del servidor.

Hubo que corregir los puertos. El enunciado pone pagos en 5002 y users en 5004; `services/run-all.sh` publica users en 5002, autores en 5003, pedidos en 5004 y pagos en 5005. Usar la tabla del enunciado habría medido otro proceso. También se excluyó `GET /login` del microservicio de login: sin cuerpo, el código rellena el administrador de demostración y abre sesión. La salud en 200 no se tomó como prueba de catálogo.

## 6. Qué cambiaría

El siguiente paso de arquitectura es servir Flask con un servidor de varios trabajadores y dejar `app.run` solo para desarrollo. Si no, el estrés mide la cola de un proceso de un hilo y no la división en microservicios. En la siguiente prueba separaría un perfil por destino, con la misma ruta y los mismos usuarios, para que el p95 de books no incluya la competencia del monolito. Alargaría el soak solo después de tener esa línea base.

## 7. Qué indican las gráficas

Los HTML de Locust, cuando existen en `evidencias/`, dibujan tres series: usuarios activos, solicitudes por segundo y percentiles de respuesta. La curva de usuarios debe seguir la rampa del perfil (escalón en stress, pico en spike, recta en soak). El RPS sube con los usuarios solo mientras el servidor absorbe la espera de 1 a 2 segundos; si el RPS se aplana mientras los usuarios siguen subiendo, hay cola. El p95 que se separa del p50 indica que unas pocas peticiones esperan mucho más que la mayoría. Esas gráficas siguen siendo la vista del cliente. No muestran CPU ni el plan de PostgreSQL. Sin el HTML o el CSV de historia de un perfil, no se describe ningún pico de esa corrida.

smoke: no hay CSV agregado, así que no hay p95 ni RPS de ese perfil. load: no hay CSV agregado, así que no hay p95 ni RPS de ese perfil. stress: no hay CSV agregado, así que no hay p95 ni RPS de ese perfil. spike: no hay CSV agregado, así que no hay p95 ni RPS de ese perfil. soak: no hay CSV agregado, así que no hay p95 ni RPS de ese perfil. breakpoint: no hay CSV agregado, así que no hay p95 ni RPS de ese perfil.
