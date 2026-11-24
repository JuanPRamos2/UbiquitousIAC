# Entrega Integrante 2 — Proceso Principal, PostgreSQL y MongoDB (Segundo Parcial)

**Responsable:** Ricardo Arath Sánchez Aguirre (#583928)  
**Equipo:** 03 — Bienestar Nexum  
**Microservicios asignados:** catalog-service y main-process-service

---

## 📦 Contenido de esta entrega

1. **Microservicios (en carpeta services/):**
   - **catalog-service (Puerto 3002):**
     - CRUD completo de unidades, instrumentos, reactivos y campañas sobre PostgreSQL 15.
     - Baja lógica (ctiva=false / ctivo=false), triggers y fechas de actualización automáticas.
     - Caché Redis con invalidación en mutaciones.
     - Soporte dual JSON y XML (Accept: application/xml o ?format=xml).
     - Sonda GET /health, Dockerfile y contrato openapi.yaml.
   - **main-process-service (Puerto 3003):**
     - Proceso central de encuestas y solicitudes de apoyo sobre MongoDB 7.
     - Cumplimiento innegociable de la regla **D-01 (cero empleado_id)**.
     - Transición de estados de solicitudes con historial append ($push).
     - Emisión de eventos operacionales en eventos_proceso.
     - Sonda GET /health, Dockerfile y contrato openapi.yaml.

2. **Base de Datos (en carpeta db/):**
   - postgres/04_catalogos_crud.sql: Migración no destructiva con triggers y constraints.
   - mongo/init.js: Índices compuestos y validación $jsonSchema.
   - scripts/evidencia/: Scripts mongosh de prueba de índices (IXSCAN) y agregaciones.

3. **Contratos XML (en carpeta contratos/xml/):**
   - catalogos.xsd y proceso.xsd: Homogeneizados con el namespace http://nexum.com.mx/bienestar/v1 y los contratos del Integrante 3.

4. **Despliegue y Orquestación (en raíz):**
   - docker-compose.microservicios.yml: Archivo listo para que el Integrante 4 lo levante junto con la infraestructura central.

5. **Documentación Completa:**
   - BITACORA_APORTACIONES_RICARDO.md: Documento maestro detallando qué, por qué y cómo se construyó cada pieza.
