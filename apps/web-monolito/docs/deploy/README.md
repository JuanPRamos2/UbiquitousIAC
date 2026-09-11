El reverse proxy recibe HTTP en el puerto 80 y reenvía a Node en 127.0.0.1:3000 conservando el prefijo /library.

Funciones: ocultar el puerto de la aplicación, terminar (en producción) TLS, servir un único origen público y evitar exponer Express a Internet.

Verificar: estáticos CSS, formularios POST, cookie de sesión con path /library, carga multipart de imágenes y redirecciones de login.
