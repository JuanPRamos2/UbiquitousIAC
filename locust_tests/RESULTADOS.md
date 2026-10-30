# Resultados Locust

Cifras leídas de `evidencias/*_stats.csv`. Donde no hay archivo, la prueba no se completó y no se rellenan p95, RPS ni errores.

Umbral: degradado si el p95 supera 1000 ms o los errores superan el 5 %.

Los puertos medidos son los del repositorio: monolito 3000, login 5000, books 5001, users 5002, autores 5003, pedidos 5004, pagos 5005.

| Perfil | Destino | Usuarios | Duración | RPS | p95 (ms) | % errores | Umbral | Hipótesis | Conclusión |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| smoke | (sin CSV) | 1 | 30 s | no disponible | no disponible | no disponible | no ejecutada | Con un usuario y pausa de 1 a 2 s espero pocas solicitudes, p95 por debajo de 1 s y casi ningún fallo si el proceso está arriba. No mide capacidad. | No se encontró `evidencias/smoke_stats.csv`. No se inventan métricas. |
| load | (sin CSV) | 5, rampa 1/s | 2 min | no disponible | no disponible | no disponible | no ejecutada | Espero latencia estable y fallos bajo el 5 %. El servidor de desarrollo de Flask atiende de uno en uno, así que la cola puede notarse frente al monolito. | No se encontró `evidencias/load_stats.csv`. No se inventan métricas. |
| stress | (sin CSV) | 2 a 20, de 2 en 2 | 3 min | no disponible | no disponible | no disponible | no ejecutada | Espero que alguna lectura cruce el umbral antes de los 20 usuarios. Ese cruce describe esta máquina y esta rampa, no el máximo real. | No se encontró `evidencias/stress_stats.csv`. No se inventan métricas. |
| spike | (sin CSV) | 2, salto a 15, vuelta a 2 | 2 min | no disponible | no disponible | no disponible | no ejecutada | Espero un empeoramiento durante la meseta de 15 y una mejora al volver a 2. La recuperación puede quedar a medias en dos minutos. | No se encontró `evidencias/spike_stats.csv`. No se inventan métricas. |
| soak | (sin CSV) | 3 | 4 min | no disponible | no disponible | no disponible | no ejecutada | Busco si el p95 o los fallos empeoran entre el tramo inicial y el final. Cuatro minutos no alcanzan para afirmar una fuga de memoria. | No se encontró `evidencias/soak_stats.csv`. No se inventan métricas. |
| breakpoint | (sin CSV) | 1 a 20, +1 cada 12 s, o hasta el umbral | máximo 4 min | no disponible | no disponible | no disponible | no ejecutada | Espero ver el primer nivel de usuarios que incumple p95 > 1 s o fallos > 5 %. Es una estimación corta. | No se encontró `evidencias/breakpoint_stats.csv`. No se inventan métricas. |

## Comprobación manual

No está `evidencias/smoke_manual.txt`. La comprobación con curl no se archivó.
