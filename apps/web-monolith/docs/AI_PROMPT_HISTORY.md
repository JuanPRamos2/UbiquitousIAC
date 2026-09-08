# AI_PROMPT_HISTORY.md

**Proyecto:** Plataforma de Bienestar Laboral y Prevención de Burnout (Proyecto 4 / IAC)

**Alumno:** Juan Pablo Ramos Salazar | Universidad de Monterrey (UDEM)

## Registro de Prompts Estratégicos y Evolución de Ingeniería

Este documento recopila las directrices y consultas clave proporcionadas a los agentes de Inteligencia Artificial a lo largo del ciclo de desarrollo. El uso de la IA se estructuró bajo un modelo de co-creación y supervisión técnica estricta, priorizando la optimización de tiempos, la solidez de la arquitectura políglota y la calidad de los entregables web.

---

### Prompt 1: Orquestación de Arquitectura Políglota y Lógica Backend (PMF)

**Objetivo técnico:** Solicitar la implementación del Producto Mínimo Funcional (PMF) conectando de manera síncrona y segura tres motores de bases de datos distintos (PostgreSQL para relaciones y seudonimización estricta, MongoDB para respuestas transaccionales y Redis para sesiones efímeras y seguridad).

**Texto del prompt:**

```text
Actúa como un Arquitecto de Software y Desarrollador Backend Senior. Tu objetivo es programar el Producto Mínimo Funcional (PMF) de una aplicación web monolítica para el "Proyecto 4. Plataforma de bienestar laboral y prevención de burnout (EQUIPO 03)". Toda la infraestructura de bases de datos (PostgreSQL, MongoDB y Redis) ya está diseñada y montada. No debes inventar esquemas nuevos; debes operar estrictamente sobre los lineamientos definidos.

Requerimientos:

- Seguridad con JWT, manejo de sesiones y contraseñas seguras con pgcrypto.
- Control de acceso diferenciado por roles (COLAB, LIDER_TURNO, AUDITOR, ADMIN_SISTEMA).
- Integración políglota estricta: PostgreSQL maneja el pivote de seudonimización (consentimiento.seudonimo), MongoDB almacena el documento embebido de respuestas_encuesta y la bitacora_auditoria sin cruces por JOIN directos, y Redis gestiona tokens revocados, caché de agregados y contadores de intentos fallidos con sus respectivos TTLs.

Genera la estructura modular completa del backend y los endpoints principales para el registro de autoreportes y auditoría asíncrona.
```

---

### Prompt 2: Refactorización UX/UI y Diseño Corporativo

**Objetivo técnico:** Elevar la presentación visual de la aplicación, eliminando trazas de depuración técnica o nombres explícitos de bases de datos en las vistas y transformándola en un entorno empresarial sobrio y profesional.

**Texto del prompt:**

```text
Actúa como un Desarrollador Frontend Senior y Especialista en UX/UI. He revisado las pantallas generadas para el Producto Mínimo Funcional (PMF) de la plataforma. La arquitectura funciona a la perfección, pero la interfaz actual expone detalles técnicos internos de la base de datos y parece un entorno de pruebas.

Tu objetivo es refactorizar las vistas web para que luzcan como un producto empresarial final, limpio y profesional:

- Elimina de las vistas cualquier mención a PostgreSQL, MongoDB, Redis, JWT o términos técnicos de backend.
- Diseña un copywriting corporativo, empático y estrictamente confidencial en los apartados de inicio de sesión y autoreportes.
- Aplica una hoja de estilos (CSS) cohesiva con una paleta de colores corporativa (verde bosque y gris) que transmita estabilidad, seguridad y bienestar, estilizando formularios, botones y controles deslizantes de forma moderna.
```

---

### Prompt 3: Estructuración y Estandarización del Workspace Web (Ubiquitous)

**Objetivo técnico:** Organizar de forma masiva los directorios independientes del semestre (ejercicio01, ejercicio02, proyecto_final) bajo una jerarquía estándar rigurosa, habilitando los árboles de carpetas web necesarios para la publicación SSH en el servidor de la UDEM.

**Texto del prompt:**

```text
Contexto y Rol: Actúa como un Ingeniero de Software, Arquitecto Cloud y Webmaster para la estructuración de entregables en la UDEM. Tengo un workspace principal con directorios dispersos de ejercicios y el proyecto final de la librería Nexus.

Objetivo: Reestructura todo el workspace para que cumpla estrictamente con la rúbrica de publicación web en ubiquitous.udem.edu.

- Renombra y estandariza los directorios a ejercicio01, ejercicio02 y proyecto_final.
- Dentro de cada uno, genera la jerarquía obligatoria de subcarpetas: /css, /img, /evidencias, /docs, /descargas (y /sql donde corresponda).
- Crea un portafolio raíz (index.html) modular y responsivo que enlace coherentemente todos los apartados del semestre e inicializa plantillas Markdown base para la documentación técnica (REQUIREMENTS.md, ENGINEERING_DECISIONS.md, SECURITY_REVIEW.md, AI_PROMPT_HISTORY.md).
```

---

### Prompt 4: Auditoría de Código y Validación de Criterios del Parcial

**Objetivo técnico:** Someter el desarrollo a una prueba de calidad estricta frente a los criterios de logro y requerimientos funcionales del primer parcial de la materia.

**Texto del prompt:**

```text
Actúa como un Auditor de Software y Arquitecto Técnico Senior. He desarrollado el Producto Mínimo Funcional (PMF) de la "Plataforma de bienestar laboral y prevención de burnout" para el primer parcial de Integración de Aplicaciones Computacionales.

Analiza el código actual y genera un reporte de auditoría crítico que contenga:

- Una checklist detallada de cumplimiento respecto a los requerimientos del primer parcial (autenticación, RBAC, catálogos y proceso principal de encuestas).
- Validación estricta de las reglas de diseño de la arquitectura políglota (aislamiento de identidades reales y uso correcto de estructuras en Redis).
- Detección de áreas de mejora en seguridad, manejo de errores y preparación para despliegue en contenedores Docker sobre Debian Linux.
```
