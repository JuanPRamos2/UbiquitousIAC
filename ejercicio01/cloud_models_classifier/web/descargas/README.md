# Clasificador de modelos Cloud — Ejercicio guiado 1

SC3705 · Integración de Aplicaciones Computacionales · Universidad de Monterrey

Esta aplicación analiza una descripción de un servicio Cloud y la clasifica como **IaaS**, **PaaS**, **SaaS** o **FaaS**.

No hace falta instalar Java ni usar la terminal para probarlo. El ejercicio corre en el navegador, en la misma página del curso.

## Cómo usarlo en el sitio

1. Entra a **Ejercicios guiados**.
2. Abre **Ejercicio guiado 1** para leer la explicación, o **Probar clasificador** para usarlo.
3. Escribe nombre, apellido y una descripción (o pulsa un ejemplo).
4. Elige **Regex + palabras clave** o **NLP básico**.
5. Pulsa **Correr clasificador**.
6. Revisa el modelo, los puntajes y la justificación.

Si un campo está vacío o el texto es muy corto, aparece un aviso.

### Textos de prueba

| Descripción | Resultado esperado |
| --- | --- |
| Necesito máquinas virtuales, almacenamiento y redes configurables para instalar mi propio sistema operativo. | IaaS |
| Quiero desplegar mi aplicación web sin administrar directamente servidores ni sistemas operativos. | PaaS |
| Los empleados utilizan una aplicación de correo electrónico directamente desde el navegador y pagan una suscripción mensual. | SaaS |
| Necesito ejecutar una función automáticamente cada vez que un usuario suba una imagen al almacenamiento Cloud. | FaaS |

## Qué hace cada motor

**Regex + palabras clave.** Busca patrones en el texto (`máquinas virtuales`, `sin administrar`, `correo electrónico`, `ejecutar una función`, etc.).

**NLP básico.** Pasa el texto por este flujo y luego asigna puntuaciones:

minúsculas → limpieza → quitar acentos → tokens → quitar stopwords → stemming → scores

No se usa un LLM para responder la categoría.

## Arquitectura

```
Visitante → Ejercicios guiados → Ejercicio 1 / Simulador
                                      → Validador
                                      → Motor Regex  o  Motor NLP
                                      → Resultado (IaaS / PaaS / SaaS / FaaS)
```

La interfaz no contiene las reglas. Cada categoría tiene su propio cálculo de puntaje. Gana quien sume más. Empate o cero evidencia → Indeterminado.

## Decisiones relevantes

- “Sin administrar servidores” cuenta como **PaaS**, no como IaaS.
- “Almacenamiento” no gana a FaaS si el texto habla de ejecutar una función al subir un archivo.

## Código compactado

En la página del ejercicio 1 hay un enlace para descargar el ZIP del proyecto (`610248_EG01_cloud_models_classifier.zip`). Incluye el código fuente y este README.

El ZIP es la entrega compactada del ejercicio. El clasificador que se evalúa en el servidor es el de esta página (simulador).
