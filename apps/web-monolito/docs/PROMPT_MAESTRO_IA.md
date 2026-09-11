# PROMPT_MAESTRO_IA.md

**Plantilla de Instrucción para Evolución Controlada con Asistencia de IA**

Utilice la siguiente estructura base para solicitar modificaciones, refactorizaciones o solución de incidencias en cualquiera de los módulos del proyecto, garantizando la trazabilidad y la responsabilidad técnica del ingeniero:

---

### Template de Solicitud

```text
Actúa como un Ingeniero de Software y Arquitecto Técnico Senior especializado en Node.js, PostgreSQL y arquitecturas web monolíticas.

Contexto actual: Estoy trabajando en el módulo [Indicar Ejercicio o Proyecto] bajo las restricciones de la materia Integración de Aplicaciones Computacionales (UDEM).
Problema / Requerimiento: [Describir brevemente qué funcionalidad se desea agregar, corregir o refactorizar].

Restricciones estrictas a considerar:
1. Mantener la separación de responsabilidades (vistas EJS, rutas, controladores, servicios y conexión a base de datos).
2. No introducir dependencias innecesarias ni romper la seguridad (uso estricto de consultas parametrizadas, hash de contraseñas y validación server-side).
3. Asegurar la compatibilidad con el despliegue local y el proxy inverso (NGINX/Apache).

Proporciona únicamente el código refactorizado o los pasos técnicos precisos, acompañados de una breve explicación de los riesgos mitigados y las pruebas recomendadas para validarlo.
```

---

### Prompt Maestro Integrador (Ejercicio 02 y carpeta de integración)

Usa este prompt en Cursor para que la IA escanee la carpeta de integración, verifique contra los requerimientos del PDF del Ejercicio 02 y ajuste lo necesario:

```text
Actúa como un Arquitecto de Software, Desarrollador Backend Senior y Auditor Técnico.

Tengo mi espacio de trabajo configurado en el repositorio local, específicamente en la carpeta denominada `integración`, la cual contiene el avance actual del Ejercicio Guiado 02 (Aplicación Web Monolítica para Gestión de una Librería utilizando Node.js, Express, EJS y PostgreSQL).

Tomando como referencia estricta los lineamientos técnicos del documento oficial del profesor (`Ejercicio-02.pdf`), necesito que actúes de la siguiente manera:

1. Escaneo y Auditoría Inicial:
   - Analiza a profundidad la estructura de archivos y el código fuente actual dentro de la carpeta `integración`.
   - Realiza un desglose claro de qué requerimientos del Ejercicio 02 ya se encuentran implementados (por ejemplo: configuración de Express, rutas base, conexión inicial a PostgreSQL, vistas EJS) y qué componentes o carpetas faltan por desarrollar (por ejemplo: esquemas completos de base de datos normalizados hasta 4FN, manejo robusto de imágenes con multer, validaciones de seguridad avanzadas, scripts SQL de procedimientos almacenados/triggers o la documentación requerida en `/docs`).

2. Refactorización y Completitud del Módulo:
   - Una vez detectadas las carencias, procede a estructurar, corregir y programar los elementos faltantes directamente en la carpeta `integración` para que el módulo quede completamente alineado con la rúbrica del Ejercicio Guiado 02.
   - Asegúrate de mantener la arquitectura monolítica server-side estricta (sin microservicios, sin APIs REST desacopladas, utilizando consultas parametrizadas con `pg` y renderizado con EJS).

Por favor, inicia escaneando el directorio, preséntame el diagnóstico de lo que tenemos y, tras esa revisión, completa lo faltante para alinear el módulo con el PDF.
```
