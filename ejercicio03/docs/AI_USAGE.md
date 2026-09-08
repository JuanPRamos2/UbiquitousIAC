# Uso de IA

Herramienta: Cursor (agente de código). El módulo SOAP se construyó en una copia de trabajo y se integró al sitio `UbiquitousIAC` como `ejercicio03/`.

## Qué se pidió

Implementar el ejercicio guiado 3 (SOAP) a partir del PDF de clase y de las diapositivas: módulo Flask independiente, WSDL, tablas propias, cliente de escritorio, Fault 409, WS-Security, interoperabilidad, reporte web e instrucciones de GCP/GitHub.

## Qué hizo la IA

- Inspeccionó el monolito Node.js y `schema.sql` (no los modificó).
- Creó `library_soap_service/` con Envelope manual, SP/vistas y privilegios.
- Extendió el clasificador Java con modo SOAP.
- Redactó el reporte `ejercicio03/` y el documento de despliegue.
- Integró el reporte al hub del sitio (mismo `style.css` y navegación) sin reorganizar `ejercicio01/`, `ejercicio02/`, `tareas/` ni `proyecto_final/`.

## Qué se revisó a mano

- El WSDL (tipos, binding, endpoint).
- Que no se reutiliza `users`.
- Que las contraseñas no salen en Faults ni en evidencias públicas.
- Que la URL de publicación es `ejercicio03` (el PDF mezcla ejercicio03 y ejercicio04).

## Prompts relevantes (resumen)

1. Analizar instrucciones + carpeta y completar el ejercicio guiado 3.
2. No modificar el monolito; dejar instrucciones GCP/GitHub si hace falta publicar.
3. Completar el reporte del ejercicio 03, las cinco tareas en casa y la página para probar el módulo SOAP en Ubiquitous.
