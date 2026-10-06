# Prompt 04: Cliente de escritorio Electron

Actúa como un Ingeniero de Software Senior especializado en Electron, Node.js, seguridad de aplicaciones de escritorio y experiencia de usuario.

## Contexto del proyecto

Trabajo en el repositorio `/home/bold/Documents/Libreria`, una solución académica para la gestión de una librería. El repositorio ya contiene:

- Una aplicación web monolítica Node.js/Express/EJS en `apps/web-monolito/`, disponible normalmente en `http://127.0.0.1:3000/library`.
- Un servicio Flask para el catálogo y las operaciones SOAP en `services/books/`, disponible normalmente en `http://127.0.0.1:5001/`.
- Un cliente de escritorio Electron en `apps/Electron_app/`.
- Scripts de arranque en la raíz: `run-library.sh`, `run-flask.sh`, `run-electron.sh` y `run.sh`.

El cliente Electron actual utiliza `main.js` para crear una ventana y cargar `start.html`. Desde el menú permite abrir la aplicación web, la interfaz SOAP y los catálogos XML/JSON. Electron debe funcionar como cliente de escritorio y punto de acceso a los servicios existentes; no debe duplicar la lógica de negocio, el acceso a PostgreSQL ni las rutas del backend.

## Objetivo

Analiza y mejora el módulo `apps/Electron_app/` para convertirlo en un cliente de escritorio funcional, mantenible y seguro para la librería, conservando la arquitectura existente y la compatibilidad con los servicios locales.

## Instrucciones de trabajo

1. Inspecciona primero `apps/Electron_app/`, los scripts de arranque de la raíz y la documentación de `apps/web-monolito/` y `services/books/`.
2. Identifica qué funcionalidades ya están implementadas y qué cambios son necesarios. No inventes endpoints: usa únicamente los endpoints existentes o documenta cualquier endpoint nuevo que sea estrictamente indispensable.
3. Mantén separadas las responsabilidades:
   - `main.js`: ciclo de vida de Electron, ventanas, menús, navegación y configuración.
   - `preload.js`, si se necesita: API mínima y explícita para el renderer.
   - HTML, CSS y JavaScript del renderer: interfaz y estado visual.
   - Node.js/Express y Flask: lógica de negocio, validaciones, persistencia y servicios.
4. Mejora la pantalla inicial para que el usuario pueda:
   - Abrir la librería web.
   - Abrir el servicio SOAP.
   - Consultar el catálogo en JSON o XML cuando el endpoint esté disponible.
   - Ver de forma clara qué servicios están disponibles y cuáles no responden.
   - Volver a la pantalla inicial sin cerrar la aplicación.
5. Centraliza las URL mediante variables de entorno con valores locales predeterminados, manteniendo compatibilidad con `LIBRARY_URL`, `SOAP_URL` y `BOOKS_JSON_URL`. Si agregas nuevas variables, documenta sus nombres y valores por defecto.
6. Gestiona errores de conexión y navegación sin bloquear ni cerrar la aplicación. La interfaz debe mostrar mensajes comprensibles y permitir reintentar.
7. Aplica buenas prácticas de seguridad de Electron:
   - Mantén `contextIsolation: true`.
   - Mantén desactivado el acceso directo a Node.js desde el renderer (`nodeIntegration: false`).
   - No uses `eval` ni cargues código remoto no confiable.
   - Controla la navegación y abre enlaces externos con `shell.openExternal` cuando corresponda.
   - No expongas secretos ni credenciales en el cliente.
8. Conserva una interfaz coherente con el proyecto, usable en Linux y con una ventana de tamaño razonable. Evita dependencias nuevas salvo que exista una justificación técnica clara.
9. Actualiza la documentación necesaria, especialmente `apps/Electron_app/README.md`, con instalación, arranque, variables de entorno, dependencias de los servicios y solución de problemas.
10. No modifiques la base de datos, el esquema SQL ni la lógica interna de la aplicación web o del servicio SOAP salvo que una incompatibilidad real del cliente lo exija.

## Validación obligatoria

Comprueba como mínimo:

- `npm install` y `npm start` dentro de `apps/Electron_app/`.
- El cliente inicia aunque los servicios todavía no estén disponibles.
- Los enlaces y elementos del menú apuntan a las URL configuradas.
- La navegación externa no se ejecuta dentro de una ventana Electron sin control.
- La aplicación muestra un estado de error y una opción de reintento cuando un servicio está detenido.
- La documentación permite a otra persona ejecutar todo el entorno desde Linux.

## Formato de respuesta

Antes de editar, presenta un diagnóstico breve y una lista concreta de archivos que modificarás. Después implementa los cambios directamente en el repositorio. Al finalizar, informa:

1. Archivos modificados y propósito de cada cambio.
2. Comandos de instalación y ejecución.
3. Pruebas realizadas y su resultado.
4. Riesgos o tareas pendientes que no puedan resolverse sin modificar los servicios backend.

Entrega código funcional, cambios mínimos y una explicación técnica breve. No reemplaces el cliente Electron por otra tecnología ni conviertas los backends existentes en APIs nuevas.