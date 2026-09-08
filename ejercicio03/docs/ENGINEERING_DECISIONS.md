# Decisiones de ingeniería

Formato: **Necesidad → Decisión → Justificación → Ventajas → Limitaciones**.

## D1. Flask / Python para el módulo SOAP

- **Necesidad:** Un servicio independiente del monolito Node.js, con construcción manual de XML.
- **Decisión:** Flask + `xml.etree.ElementTree` + `psycopg2`.
- **Justificación:** El enunciado prohíbe Spyne/Zeep en el servidor. Flask expone un POST HTTP sin generar el Envelope.
- **Ventajas:** Control total del XML, pocas dependencias, fácil de explicar en clase.
- **Limitaciones:** Más código boilerplate que un framework SOAP; hay que cuidar namespaces y Faults a mano.

## D2. SOAP 1.1 + WSDL document/literal

- **Necesidad:** Contrato interoperable antes de programar clientes.
- **Decisión:** WSDL 1.1, binding SOAP 1.1, estilo document/literal wrapped, tipos XSD (incluye enumeración CloudModelo).
- **Justificación:** Es el perfil que `wsimport`, `dotnet-svcutil` y zeep siguen entendiendo. El tipado evita “todo es texto”.
- **Ventajas:** Clientes en otro lenguaje se generan del contrato; cambios incompatibles se ven en el WSDL.
- **Limitaciones:** Evolucionar el contrato (campo obligatorio nuevo) rompe clientes; versionar es más rígido que REST.

## D3. Acceso directo a PostgreSQL con privilegio mínimo

- **Necesidad:** Leer el catálogo real y persistir clasificaciones sin tocar el código Node.
- **Decisión:** Rol `soap_user`, vistas y stored procedures; SELECT sobre catálogo; INSERT/UPDATE sólo en tablas SOAP.
- **Justificación:** Compartir BD es un atajo académico. El rol no ve `users.password_hash`.
- **Ventajas:** Integridad con FK a `books.isbn` y `concepts.id`; transacciones y rollback reales.
- **Limitaciones:** Acoplamiento al esquema del monolito. Si mañana se renombra `isbn`, el módulo se rompe.

## D4. Tablas propias (`clasificadores`, no `users`)

- **Necesidad:** Identificar al clasificador SOAP sin contaminar el modelo de autenticación web.
- **Decisión:** Tabla `clasificadores` con nombre, apellidos y correo. No se inserta en `users`.
- **Justificación:** `users` exige `password_hash` y roles `admin|client`. Un clasificador de escritorio no es un usuario del monolito.
- **Ventajas:** El monolito sigue intacto; no hay cuentas huérfanas ni violación del índice de un solo admin.
- **Limitaciones:** Dos identidades (web vs SOAP) para la misma persona. El correo SOAP no está verificado.

## D5. Envelope construido a mano

- **Necesidad:** Demostrar Envelope, Header, Body y namespaces.
- **Decisión:** `xml.etree` en el servidor y DOM en Java. Cero concatenación de XML.
- **Justificación:** Concatenar strings permitiría inyección XML y rompe el aprendizaje del protocolo.
- **Ventajas:** Se ve qué es boilerplate y qué cambia por operación; los valores se escapan.
- **Limitaciones:** Más verboso; un Spyne ahorraría tiempo en un sistema real.

## D6. Autenticación WS-Security sólo en estadísticas

- **Necesidad:** Extender el contrato sin romper las tres operaciones iniciales, y proteger un dato agregado.
- **Decisión:** UsernameToken (usuario/contraseña) en el Header de `ObtenerEstadisticasPorModelo`. Contraseña verificada con PBKDF2; nunca se guarda en claro en evidencias.
- **Justificación:** Las operaciones de clasificación del laboratorio identifican al usuario por correo. Las estadísticas globales sí merecen un secreto compartido.
- **Ventajas:** Compatibilidad hacia atrás; se demuestra Header vs Body.
- **Limitaciones:** UsernameToken en claro requiere TLS en producción. El correo del clasificador no es autenticación.

## D7. SOAP Fault con código 409 en el detalle

- **Necesidad:** El cliente debe distinguir duplicado, validación y falla interna.
- **Decisión:** Fault en el Body; `detail/codigo` 400, 409, 404, 401 o 500; HTTP alineado con ese código. Sin SQL ni stack traces en el XML.
- **Justificación:** SOAP no se apoya sólo en el status HTTP: el Fault es parte del contrato. El 409 vive en el detalle para que la GUI lo interprete.
- **Ventajas:** La app de escritorio muestra un mensaje útil distinto para 409 (cliente) y 500 (servidor).
- **Limitaciones:** Algunos stacks SOAP clásicos esperan siempre HTTP 500. Aquí se documenta la decisión académica.

## D8. Interoperabilidad WSDL-first

- **Necesidad:** Probar que el contrato no es “el XML que se me ocurrió”, sino un servicio consumible.
- **Decisión:** Cliente Java manual (DOM) + cliente Python zeep generado desde el WSDL.
- **Justificación:** El servidor es Python artesanal; zeep demuestra que otro stack puede hablarle sin conocer Flask.
- **Ventajas:** Evidencia reproducible; comparación de boilerplate vs librería.
- **Limitaciones:** zeep es sensible a details del WSDL; un desajuste de namespaces se nota al instante.
