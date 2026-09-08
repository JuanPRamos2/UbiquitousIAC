# AI_CHANGELOG.md

**Proyecto:** Portafolio Académico e Ingeniería de Software (IAC)

**Alumno:** Juan Pablo Ramos Salazar | Universidad de Monterrey (UDEM)

Este documento registra de forma cronológica las modificaciones, refactorizaciones y evoluciones arquitectónicas implementadas con asistencia de Inteligencia Artificial en los módulos del semestre (`ejercicio01`, `ejercicio02` y `proyecto_final`).

---

### [2026-08-30] · Estructuración Global y Adaptación a Servidor Ubiquitous

- **Cambio:** Reorganización completa de la jerarquía de directorios del workspace a partir de los repositorios independientes (`IAC2`, `integración`, `IAC`).
- **Implementación:** Creación de las subcarpetas estándar exigidas por la UDEM (`/css`, `/img`, `/evidencias`, `/docs`, `/descargas`, `/sql`) en cada módulo.
- **Impacto:** Estandarización de rutas web relativas y preparación del empaquetado `.tar.gz` para la subida limpia mediante SSH al servidor personal.

### [2026-09-02] · Refactorización UX/UI y Blindaje de Interfaz (Proyecto 4)

- **Cambio:** Eliminación de trazas de depuración técnica en las vistas del Producto Mínimo Funcional (PMF).
- **Implementación:** Supresión de nombres explícitos de motores de bases de datos (`PostgreSQL`, `MongoDB`, `Redis`) en los encabezados de usuario final; integración de una paleta de colores corporativa (verde bosque/gris) y adaptación de un *copywriting* enfocado en la estricta confidencialidad y anonimización.
- **Impacto:** Transición de un entorno de pruebas técnicas a una interfaz web empresarial lista para demostración ejecutiva.

### [2026-09-03] · Consolidación del Monolito Server-Side y Persistencia Políglota

- **Cambio:** Sincronización del motor de la aplicación web de gestión (librería / plataforma) con los esquemas relacionales y no relacionales.
- **Implementación:** Integración de controladores en Node.js/Express interactuando directamente mediante consultas parametrizadas, gestión de sesiones con JWT y control de acceso diferenciado por roles (`COLAB`, `LIDER_TURNO`, `AUDITOR`, `ADMIN_SISTEMA`).
- **Impacto:** Cumplimiento total de las restricciones arquitectónicas del Ejercicio Guiado 02 y robustecimiento de la seguridad ante inyecciones SQL y accesos no autorizados.
