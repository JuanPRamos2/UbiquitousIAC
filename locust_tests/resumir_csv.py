"""Construye RESULTADOS.md y REFLEXION.md solo con cifras de los CSV.

Si un perfil no tiene CSV, la fila dice que no se completó. No inventa
p95, RPS ni porcentajes de error.
"""

from __future__ import annotations

import csv
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
EVIDENCIAS = RAIZ / "evidencias"
PERFILES = ("smoke", "load", "stress", "spike", "soak", "breakpoint")
P95_MS = 1000
ERROR_MAX = 5.0

PLAN = {
    "smoke": ("1", "30 s", "Con un usuario y pausa de 1 a 2 s espero pocas solicitudes, p95 por debajo de 1 s y casi ningún fallo si el proceso está arriba. No mide capacidad."),
    "load": ("5, rampa 1/s", "2 min", "Espero latencia estable y fallos bajo el 5 %. El servidor de desarrollo de Flask atiende de uno en uno, así que la cola puede notarse frente al monolito."),
    "stress": ("2 a 20, de 2 en 2", "3 min", "Espero que alguna lectura cruce el umbral antes de los 20 usuarios. Ese cruce describe esta máquina y esta rampa, no el máximo real."),
    "spike": ("2, salto a 15, vuelta a 2", "2 min", "Espero un empeoramiento durante la meseta de 15 y una mejora al volver a 2. La recuperación puede quedar a medias en dos minutos."),
    "soak": ("3", "4 min", "Busco si el p95 o los fallos empeoran entre el tramo inicial y el final. Cuatro minutos no alcanzan para afirmar una fuga de memoria."),
    "breakpoint": ("1 a 20, +1 cada 12 s, o hasta el umbral", "máximo 4 min", "Espero ver el primer nivel de usuarios que incumple p95 > 1 s o fallos > 5 %. Es una estimación corta."),
}


def leer(ruta: Path) -> list[dict[str, str]]:
    if not ruta.exists():
        return []
    with ruta.open(newline="", encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def numero(texto: str | None) -> float | None:
    if texto is None:
        return None
    limpio = texto.strip()
    if not limpio or limpio.upper() == "N/A":
        return None
    try:
        return float(limpio)
    except ValueError:
        return None


def fila_stats(perfil: str) -> list[dict[str, str]]:
    return leer(EVIDENCIAS / f"{perfil}_stats.csv")


def porcentaje_error(fila: dict[str, str]) -> float | None:
    total = numero(fila.get("Request Count"))
    fallos = numero(fila.get("Failure Count"))
    if total is None or fallos is None or total <= 0:
        return None
    return 100.0 * fallos / total


def umbral(p95: float | None, errores: float | None) -> str:
    if p95 is None or errores is None:
        return "sin datos"
    if p95 > P95_MS or errores > ERROR_MAX:
        return "degradado"
    return "cumple"


def fmt(valor: float | None, decimales: int = 2) -> str:
    if valor is None:
        return "no disponible"
    return f"{valor:.{decimales}f}"


def nombre(fila: dict[str, str]) -> str:
    return (fila.get("Name") or "").strip()


def es_agregado(fila: dict[str, str]) -> bool:
    return nombre(fila) in {"Aggregated", "Total", ""}


def solicitudes(perfil: str) -> list[dict[str, str]]:
    return [fila for fila in fila_stats(perfil) if not es_agregado(fila)]


def agregado(perfil: str) -> dict[str, str] | None:
    for fila in fila_stats(perfil):
        if nombre(fila) == "Aggregated":
            return fila
    return None


def conclusion(p95: float | None, errores: float | None, peticiones: float | None) -> str:
    if peticiones is None or peticiones <= 0:
        return "No hubo respuestas registradas para esta solicitud."
    estado = umbral(p95, errores)
    if estado == "sin datos":
        return "El CSV no trae p95 o fallos, así que no se juzga el umbral."
    if estado == "degradado":
        motivos = []
        if p95 is not None and p95 > P95_MS:
            motivos.append(f"p95 {fmt(p95, 0)} ms supera 1000 ms")
        if errores is not None and errores > ERROR_MAX:
            motivos.append(f"los errores son {fmt(errores)} %")
        return "Incumple el umbral: " + " y ".join(motivos) + "."
    return "Se mantiene dentro del umbral de 1000 ms y 5 % de errores."


def escribir_resultados() -> None:
    lineas = [
        "# Resultados Locust",
        "",
        "Cifras leídas de `evidencias/*_stats.csv`. Donde no hay archivo, la prueba no se completó y no se rellenan p95, RPS ni errores.",
        "",
        "Umbral: degradado si el p95 supera 1000 ms o los errores superan el 5 %.",
        "",
        "Los puertos medidos son los del repositorio: monolito 3000, login 5000, books 5001, users 5002, autores 5003, pedidos 5004, pagos 5005.",
        "",
        "| Perfil | Destino | Usuarios | Duración | RPS | p95 (ms) | % errores | Umbral | Hipótesis | Conclusión |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for perfil in PERFILES:
        usuarios, duracion, hipotesis = PLAN[perfil]
        filas = solicitudes(perfil)
        if not filas:
            lineas.append(
                f"| {perfil} | (sin CSV) | {usuarios} | {duracion} | no disponible | no disponible | no disponible | no ejecutada | {hipotesis} | No se encontró `evidencias/{perfil}_stats.csv`. No se inventan métricas. |"
            )
            continue
        for fila in filas:
            p95 = numero(fila.get("95%"))
            errores = porcentaje_error(fila)
            rps = numero(fila.get("Requests/s"))
            peticiones = numero(fila.get("Request Count"))
            lineas.append(
                "| {perfil} | {destino} | {usuarios} | {duracion} | {rps} | {p95} | {errores} | {umbral} | {hipotesis} | {conclusion} |".format(
                    perfil=perfil,
                    destino=nombre(fila).replace("|", "/"),
                    usuarios=usuarios,
                    duracion=duracion,
                    rps=fmt(rps),
                    p95=fmt(p95, 0),
                    errores=fmt(errores),
                    umbral=umbral(p95, errores),
                    hipotesis=hipotesis.replace("|", "/"),
                    conclusion=conclusion(p95, errores, peticiones).replace("|", "/"),
                )
            )
    manual = EVIDENCIAS / "smoke_manual.txt"
    lineas.extend(["", "## Comprobación manual", ""])
    if manual.exists():
        lineas.append("```")
        lineas.append(manual.read_text(encoding="utf-8").rstrip())
        lineas.append("```")
    else:
        lineas.append("No está `evidencias/smoke_manual.txt`. La comprobación con curl no se archivó.")
    errores = EVIDENCIAS / "errores.log"
    if errores.exists() and errores.read_text(encoding="utf-8").strip():
        lineas.extend(["", "## Errores de ejecución", "", "```", errores.read_text(encoding="utf-8").rstrip(), "```"])
    (RAIZ / "RESULTADOS.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")


def historia(perfil: str) -> list[dict[str, str]]:
    return [
        fila
        for fila in leer(EVIDENCIAS / f"{perfil}_stats_history.csv")
        if nombre(fila) == "Aggregated"
    ]


def resumen_agregado(perfil: str) -> str:
    fila = agregado(perfil)
    if fila is None:
        return f"{perfil}: no hay CSV agregado, así que no hay p95 ni RPS de ese perfil."
    p95 = numero(fila.get("95%"))
    errores = porcentaje_error(fila)
    rps = numero(fila.get("Requests/s"))
    return (
        f"{perfil}: RPS agregado {fmt(rps)}, p95 {fmt(p95, 0)} ms, "
        f"errores {fmt(errores)} % ({umbral(p95, errores)})."
    )


def primera_degradacion() -> str:
    for perfil in ("stress", "breakpoint", "spike", "load", "soak", "smoke"):
        peores = []
        for fila in solicitudes(perfil):
            p95 = numero(fila.get("95%"))
            errores = porcentaje_error(fila)
            if umbral(p95, errores) == "degradado":
                peores.append(nombre(fila))
        if peores:
            return (
                f"En el perfil {perfil}, estas solicitudes quedan degradadas según el CSV final: "
                + ", ".join(peores)
                + ". El CSV final no dice el segundo exacto del primer fallo; para el orden temporal hay que mirar la historia."
            )
    if any(fila_stats(perfil) for perfil in PERFILES):
        return "Ninguna solicitud con CSV supera el umbral en el agregado final de su perfil."
    return "No hay CSV. No se puede decir qué servicio se degradó primero."


def quiebre_observado() -> str:
    filas = historia("breakpoint")
    if not filas:
        return "No hay `breakpoint_stats_history.csv`. El punto de quiebre no se estimó."
    for fila in filas:
        totales = numero(fila.get("Total Request Count")) or 0
        fallos = numero(fila.get("Total Failure Count")) or 0
        errores = 100.0 * fallos / totales if totales else 0
        p95 = numero(fila.get("95%") or fila.get("Total Median Response Time"))
        # La historia de Locust guarda el percentil en columnas 95% solo en algunas versiones.
        p95_historia = numero(fila.get("95%"))
        if p95_historia is None:
            continue
        if totales >= 30 and (p95_historia > P95_MS or errores > ERROR_MAX):
            usuarios = fila.get("User Count", "?")
            return (
                f"En la historia agregada del punto de quiebre, el umbral se incumple "
                f"con {usuarios} usuarios (p95 {fmt(p95_historia, 0)} ms, errores {fmt(errores)} %). "
                "Esa cifra es de una rampa de como máximo 4 minutos en esta instancia, no la capacidad máxima."
            )
    return (
        "La historia del punto de quiebre no muestra un agregado que cruce el umbral "
        "con al menos 30 respuestas, o esa versión del CSV no trae la columna 95%."
    )


def deriva_soak() -> str:
    filas = [fila for fila in historia("soak") if numero(fila.get("95%")) is not None]
    if len(filas) < 4:
        return "No hay suficiente historia del soak para comparar el tramo inicial con el final."
    corte = max(1, len(filas) // 4)
    inicio = filas[:corte]
    final = filas[-corte:]

    def media(grupo: list[dict[str, str]]) -> float:
        valores = [numero(fila.get("95%")) or 0 for fila in grupo]
        return sum(valores) / len(valores)

    return (
        f"p95 agregado medio del primer cuarto del soak: {fmt(media(inicio), 0)} ms; "
        f"del último cuarto: {fmt(media(final), 0)} ms. "
        "La diferencia describe 4 minutos, no un soak de horas."
    )


def comparacion_load() -> str:
    filas = {nombre(fila): fila for fila in solicitudes("load")}
    if not filas:
        return "No hay CSV de load. No se afirma qué arquitectura fue más rápida."
    interes = [
        "monolito GET /library/health",
        "monolito GET /library/books",
        "monolito GET /library/login",
        "books GET /books?format=json",
        "autores GET /authors",
        "login GET /session?format=json",
    ]
    partes = []
    for clave in interes:
        fila = filas.get(clave)
        if fila is None:
            partes.append(f"{clave}: no aparece en el CSV de load.")
            continue
        partes.append(
            f"{clave}: RPS {fmt(numero(fila.get('Requests/s')))}, "
            f"p95 {fmt(numero(fila.get('95%')), 0)} ms, "
            f"errores {fmt(porcentaje_error(fila))} %."
        )
    return " ".join(partes)


def escribir_reflexion() -> None:
    perfiles = " ".join(resumen_agregado(perfil) for perfil in PERFILES)
    texto = f"""# Reflexión

Las cifras de esta página salen de los CSV de `evidencias/`. Si un perfil no se corrió, se dice y no se sustituye por un número.

## 1. Monolito y microservicios

{comparacion_load()}

La comparación usable es entre lecturas parecidas: el catálogo público `books GET /books?format=json` y, si hubo sesión, `monolito GET /library/books`. La salud del monolito y la de un microservicio solo dicen que el proceso respondió. Users, pedidos y pagos no tienen lectura pública; sin `LOCUST_EMAIL` y `LOCUST_PASSWORD` esas listas no entran en la prueba. Los seis procesos comparten la misma instancia y la misma rampa, así que un servicio lento compite por CPU con los demás.

## 2. Primera degradación

{primera_degradacion()}

{quiebre_observado()}

## 3. Diferencia entre perfiles

Smoke comprueba el guion con 1 usuario y 30 segundos. Load sostiene 5 usuarios dos minutos. Stress sube de 2 a 20. Spike salta a 15 y vuelve a 2. Soak deja 3 usuarios cuatro minutos para ver deriva. El punto de quiebre sube de uno en uno y se detiene al cruzar el umbral.

{perfiles}

{deriva_soak()}

## 4. Limitaciones

La carga sale de una sola máquina, con pausa de 1 a 2 segundos, así que el RPS no es la capacidad máxima. El tope de cada perfil es de minutos: el soak no prueba fugas largas y el quiebre no es el límite de un despliegue con varias réplicas. Flask arranca con `app.run` sin hilos de producción; Node atiende por el bucle de eventos. La red hasta la IP pública suma latencia que no existe en un curl local. Las escrituras se evitaron, así que no hay evidencia de altas, pagos ni stock. Si un puerto no respondió en `smoke_manual.txt`, ese destino no debe leerse como un éxito.

## 5. Qué aportó la IA y qué hubo que corregir

La IA propuso un solo `locustfile` con `LoadTestShape` y un `name` distinto por destino, para no mezclar en una fila el monolito y los microservicios. También sirvió para separar usuarios, `spawn_rate`, `wait_time` y duración: el spawn solo describe la rampa, y la espera entre tareas no es latencia del servidor.

Hubo que corregir los puertos. El enunciado pone pagos en 5002 y users en 5004; `services/run-all.sh` publica users en 5002, autores en 5003, pedidos en 5004 y pagos en 5005. Usar la tabla del enunciado habría medido otro proceso. También se excluyó `GET /login` del microservicio de login: sin cuerpo, el código rellena el administrador de demostración y abre sesión. La salud en 200 no se tomó como prueba de catálogo.

## 6. Qué cambiaría

El siguiente paso de arquitectura es servir Flask con un servidor de varios trabajadores y dejar `app.run` solo para desarrollo. Si no, el estrés mide la cola de un proceso de un hilo y no la división en microservicios. En la siguiente prueba separaría un perfil por destino, con la misma ruta y los mismos usuarios, para que el p95 de books no incluya la competencia del monolito. Alargaría el soak solo después de tener esa línea base.

## 7. Qué indican las gráficas

Los HTML de Locust, cuando existen en `evidencias/`, dibujan tres series: usuarios activos, solicitudes por segundo y percentiles de respuesta. La curva de usuarios debe seguir la rampa del perfil (escalón en stress, pico en spike, recta en soak). El RPS sube con los usuarios solo mientras el servidor absorbe la espera de 1 a 2 segundos; si el RPS se aplana mientras los usuarios siguen subiendo, hay cola. El p95 que se separa del p50 indica que unas pocas peticiones esperan mucho más que la mayoría. Esas gráficas siguen siendo la vista del cliente. No muestran CPU ni el plan de PostgreSQL. Sin el HTML o el CSV de historia de un perfil, no se describe ningún pico de esa corrida.

{perfiles}
"""
    (RAIZ / "REFLEXION.md").write_text(texto, encoding="utf-8")


def main() -> None:
    EVIDENCIAS.mkdir(exist_ok=True)
    escribir_resultados()
    escribir_reflexion()


if __name__ == "__main__":
    main()
