# Plan de pruebas

Cada caso: ID, requisito, precondición, entrada, pasos, esperado, observado (a completar en la VM), estado, evidencia.

| ID | Requisito | Precondición | Entrada | Pasos | Esperado | Observado | Estado | Evidencia |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T-01 | RF-02 | Usuario seed | admin@library.local + clave seed | Login | Dashboard | | Pendiente | screenshot login |
| T-02 | RF-03 | Sesión abierta | POST logout | Cerrar sesión | Redirect login; catálogo inaccesible | | Pendiente | screenshot |
| T-03 | RF-05 | Autenticado | ISBN `9780134444245` | Buscar | Solo Cloud Computing | | Pendiente | screenshot |
| T-04 | RF-06 | Autenticado | título `cloud` | Buscar | Libro de Cloud Computing | | Pendiente | screenshot |
| T-05 | RF-08 | Admin | alta de libro válida | Crear | Mensaje de éxito y ficha | | Pendiente | screenshot |
| T-06 | RF-08 | Admin | editar precio | Guardar | Precio persistido | | Pendiente | screenshot |
| T-07 | RF-08 | Admin | eliminar libro sintético | Confirmar | Desaparece del catálogo | | Pendiente | screenshot |
| T-08 | RF-09 | Admin | nuevo autor | CRUD autores | Autor listado | | Pendiente | screenshot |
| T-09 | RF-10 | Admin | nuevo género | CRUD géneros | Género listado | | Pendiente | screenshot |
| T-10 | RF-11 | Admin | nuevo formato | CRUD formatos | Formato listado | | Pendiente | screenshot |
| T-11 | RF-12 | Admin | nueva categoría | CRUD categorías | Categoría listada | | Pendiente | screenshot |
| T-12 | RF-13 | Admin | nuevo concepto | CRUD conceptos | Concepto listado | | Pendiente | screenshot |
| T-13 | RF-14 | Admin | dos autores en un libro | Guardar | Ambos en ficha | | Pendiente | screenshot |
| T-14 | RF-15 | Admin | dos géneros | Guardar | Ambos en ficha | | Pendiente | screenshot |
| T-15 | RF-16 | Admin | IaaS con cap. y pág. | Conceptos del libro | Definición visible | | Pendiente | screenshot Cloud |
| T-16 | RF-17 | Admin | JPG < 5 MB | Subir y marcar portada | Portada y alt persistidos | | Pendiente | screenshot |
| T-17 | RF-19 | Usuario client | GET `/library/books/new` | Abrir | 403 | | Pendiente | screenshot |
| T-18 | RF-19 | Visitante | GET `/library/books` | Abrir incógnito | Redirect login | | Pendiente | screenshot |
| T-19 | RF-20 | Ya hay un admin | INSERT segundo admin | psql | ERROR unique/trigger | | Pendiente | salida psql |
| T-20 | RNF-01 | Autenticado | búsqueda `' OR 1=1 --` | Buscar título | No dump de toda la tabla por inyección | | Pendiente | screenshot |
| T-21 | RF-18 | psql | stock -1 | INSERT | check_violation | | Pendiente | salida psql |
| T-22 | RF-18 | psql | precio -1 | INSERT | check_violation | | Pendiente | salida psql |
| T-23 | RNF-03 | psql | ISBN duplicado | INSERT | unique_violation | | Pendiente | salida psql |
| T-24 | RNF-03 | psql | format_id 999999 | INSERT | foreign_key_violation | | Pendiente | salida psql |
| T-25 | RNF-03 | psql | DELETE format en uso | DELETE | RESTRICT | | Pendiente | salida psql |
| T-26 | RF-17 | Admin | archivo `.php` | Subir | Rechazo controlado | | Pendiente | screenshot |
| T-27 | RNF-06 | Node en 127.0.0.1 | URL pública `/library` | Navegador externo | Reverse proxy sirve HTML | | Pendiente | screenshot |
| T-28 | RNF-05 | Autenticado | navegar catálogo → ficha → perfil | Clics | Layout coherente bajo `/library` | | Pendiente | screenshot |
| T-29 | RF-01 | Visitante | registro válido | POST register | Sesión client | | Pendiente | screenshot |
| T-30 | RF-01 | Visitante | clave `123` | POST register | Rechazo de política | | Pendiente | screenshot |

Las capturas se añaden en la página de evidencias al publicar. Una captura sin este ID no cuenta como prueba.
