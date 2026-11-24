# Atlas: catálogo Electron

Aplicación de escritorio para Arch Linux que muestra el catálogo de libros desde un microservicio XML configurable. La interfaz está organizada por módulos MVC:

- `src/models/`: configuración persistida y repositorio XML.
- `src/views/`: HTML, estilos y componentes de presentación.
- `src/controllers/`: eventos, carga por página y coordinación del modelo/vista.
- `src/main.js` y `src/preload.js`: proceso principal de Electron con `contextIsolation` activo.

## Requisitos

- Arch Linux (probado conceptualmente para kitty).
- Node.js y npm.
- Acceso de red al microservicio XML.

## Ejecución

```bash
cd apps/Electron_app
npm install
npm start
```

Para comprobar la sintaxis de los módulos:

```bash
npm run check
```

La configuración inicial apunta a `http://34.51.99.221:5001/books`. Desde **Configuración** se pueden cambiar la URL base, el endpoint y la cantidad de títulos por página. Los valores se guardan con `localStorage` y se reutilizan al abrir la aplicación.

El cliente solicita exclusivamente `application/xml`/`text/xml`, convierte el XML con `DOMParser` y no consume endpoints JSON. En cada cambio de página envía `page` y `limit`; si el servicio entrega el catálogo completo, el cliente aplica la paginación sobre esa respuesta XML.
