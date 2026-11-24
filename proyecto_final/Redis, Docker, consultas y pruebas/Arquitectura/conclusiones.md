# Conclusiones de la esta parte

Se agregaron dos microservicios de solo lectura al sistema que el equipo ya tenía, sin reemplazar la web ni el esquema de Bienestar Nexum. Consultas responde catálogos, bitácora, intervenciones y vistas protegidas. Reportes arma series para Highcharts con conteos reales. Redis quedó como componente común: sesión, revocación, caché con TTL, contadores, límite de peticiones y un lock de estampida. Docker Compose levanta la web, las dos APIs, PostgreSQL, MongoDB y Redis en una sola red.

Se diseñó así porque el dominio ya prohíbe leer respuestas individuales y porque el cálculo con ruido de Laplace gasta un presupuesto. Duplicar ese cálculo en reportes habría sido incorrecto. Por eso el servicio de reportes lee lo publicado y, si todavía no hay filas, lo dice en lugar de inventar números. La gráfica que sí tiene datos de inmediato es la de campañas por estado: 1 abierta y 3 cerradas, salida de `GROUP BY`.

El problema que apareció al probar los contenedores fue que Express 4 no captura una excepción lanzada dentro de una ruta `async`. Un 400 y un 403 tiraban el proceso. Se envolvió cada ruta con el manejador de errores y se volvió a construir la imagen. Después de eso, la integración contra los contenedores pasó los casos de éxito, parámetro inválido, registro inexistente, 401, 403, 404, 422, 429, XML, caché HIT/MISS, PostgreSQL y MongoDB.

También se comprobó que un token emitido por el login real del monolito abre consultas y reportes, y que la página `consultas-reportes.html` dibuja la serie con Highcharts.

Queda pendiente de los otros integrantes extraer auth, usuarios, catálogo, proceso principal, documentos y notificaciones a sus propios contenedores. El contrato para enganchar Auth Service ya está: mismo secreto o llave pública, mismos claims y las claves `session:{jti}` y `revoked:{jti}`. Queda también pendiente que el proceso principal publique filas en `agregado.resultado_protegido` si se quiere ver la serie de valor protegido con números; la participación suficiente de la unidad del líder ya se puede mostrar sin ese paso y sin revelar el tamaño del grupo.
