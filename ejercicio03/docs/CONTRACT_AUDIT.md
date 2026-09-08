# Auditoría del contrato WSDL

Regla: el contrato expone capacidades y datos necesarios, no la estructura completa de la BD.

## Tabla dato → operación → exposición → justificación

| Dato | Origen | Operación | ¿Se expone? | Justificación |
| --- | --- | --- | --- | --- |
| conceptId | `concepts.id` | ObtenerConceptosPendientes, RegistrarClasificacion | Sí (int) | Clave para registrar sin ambigüedad. |
| conceptName | `concepts.name` | ObtenerConceptosPendientes | Sí | El usuario identifica qué clasifica. |
| definition | `book_concepts.definition` | ObtenerConceptosPendientes | Sí | Texto que el motor local clasifica. |
| isbn | `books.isbn` | Pendientes / Registrar | Sí | Identifica el libro en el catálogo. |
| bookTitle | `books.title` | ObtenerConceptosPendientes | Sí | Contexto humano; no se expone el `books.id` interno. |
| categoryName | `categories.name` | ObtenerConceptosPendientes | Sí | Permite clasificar conceptos de varias categorías. |
| modelo | valor del módulo SOAP | Registrar / Estadísticas | Sí (enum XSD) | Resultado de negocio. |
| nombre, apellidos, correo | cliente SOAP → `clasificadores` | Registrar / Progreso | Sí | Identidad del clasificador. No es la tabla `users`. |
| price, stock | `books` | ninguna | No | No hacen falta para clasificar; son datos comerciales. |
| password_hash, role | `users` | ninguna | No | Superficie de ataque. El módulo ni siquiera tiene GRANT. |
| books.id, format_id | `books` | ninguna | No | Sustituidos por ISBN y nombres de negocio. |
| credenciales de BD | `.env` | ninguna | No | Secretos de infraestructura. |
| SQL, stack traces | logs del servidor | Fault | No | El Fault lleva mensaje + código, no la consulta. |
| conteo por modelo | `clasificaciones_cloud` | ObtenerEstadisticasPorModelo | Sí, protegido | Agregado; no lista personas. Requiere WS-Security. |

## Tres riesgos y mitigación

1. **WSDL público revela operaciones y tipos.** Un atacante ve cómo invocar `RegistrarClasificacion`. Mitigación: no publicar el endpoint a Internet sin TLS; proteger estadísticas; en producción, WSDL autenticado o red privada.
2. **El correo del cliente se cree a ciegas.** Quien conozca un correo puede consultar progreso o intentar duplicados. Mitigación académica: suficiente para el laboratorio. En producción: WS-Security o tokens en todas las operaciones.
3. **Acoplamiento a `isbn` y `concepts.id`.** Un rename en el monolito rompe el módulo. Mitigación: la vista `v_catalogo_conceptos` concentra el acoplamiento; se podría sustituir por una réplica o API interna más adelante.

## Conclusión

El contrato es estricto (XSD + enum + mensajes nombrados) y por eso es mantenible: un campo obligatorio nuevo se ve en el WSDL. También es deliberadamente estrecho: oculta usuarios, precios y claves internas. Esa estrechez es la decisión de ingeniería, no un olvido.
