# Por qué sigue siendo un monolito

El flujo de ejecución es:

Navegador → Apache/NGINX → proceso Node.js (Express) → middleware → rutas → servicios → PostgreSQL / disco `uploads/`.

Presentación (EJS), lógica de negocio (services) y acceso a datos (`pg` + SP) viven **en el mismo proceso y el mismo artefacto desplegable**. Dividir carpetas (`routes/`, `services/`, `middleware/`) es organización interna, no distribución.

El reverse proxy no es un microservicio: termina HTTP público y reenvía a `127.0.0.1:3000`. PostgreSQL es el motor de datos, no un “servicio de librería” con API propia.

Diagrama: `img/ARCHITECTURE_MONOLITHIC.svg`.
