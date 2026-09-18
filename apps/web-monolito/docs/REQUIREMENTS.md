# Requisitos — Librería monolítica

**Proyecto:** Ejercicio guiado 02  
**Estudiante:** Juan Pablo Ramos Salazar · 610248  
**Alcance:** aplicación web monolítica server-side para gestionar una librería en línea.

## Supuestos

- Existe un entorno GCP Compute Engine con CentOS Stream 10, PostgreSQL y Node.js.
- Los usuarios finales acceden con un navegador; no hay clientes móviles nativos ni APIs públicas.
- El único administrador es un usuario de negocio de la librería, no un rol de sistema operativo.
- Las imágenes se almacenan en disco de la misma instancia; PostgreSQL guarda metadatos y el nombre de archivo generado.

## Restricciones

- Monolito Node.js + Express + EJS. Sin REST, GraphQL, SOAP ni microservicios.
- Sin JSON/XML como mecanismo de intercambio entre frontend y backend.
- Acceso a PostgreSQL con `pg` y SQL parametrizado / stored procedures.
- Como máximo un Administrador, también reforzado en la base de datos.
- Node escucha en `127.0.0.1:3000`; el acceso público es `/library` vía Apache o NGINX.

## Requisitos funcionales

| ID | Requisito | Criterio de aceptación |
| --- | --- | --- |
| RF-01 | Registro de usuarios | Un visitante puede crear una cuenta con nombre, correo y contraseña válida. La contraseña se guarda con hash. El rol resultante es `client`. |
| RF-02 | Inicio de sesión | Un usuario registrado accede con correo y contraseña correctos y obtiene una sesión. Credenciales inválidas muestran un mensaje controlado. |
| RF-03 | Cierre de sesión | El usuario autenticado puede cerrar sesión y deja de acceder a rutas privadas. |
| RF-04 | Consulta del catálogo | Un usuario autenticado ve el listado de libros (ISBN, título, precio, stock, autores, portada). |
| RF-05 | Búsqueda por ISBN | El catálogo filtra por coincidencia parcial de ISBN. |
| RF-06 | Búsqueda por título | El catálogo filtra por coincidencia parcial de título (sin distinguir mayúsculas). |
| RF-07 | Detalle de libro | El usuario autenticado ve ficha con autores, géneros, formato, categoría, stock, precio, conceptos e imágenes. |
| RF-08 | CRUD de libros | El Administrador crea, consulta, edita y elimina libros desde la interfaz web, con validación server-side. |
| RF-09 | CRUD de autores | El Administrador administra el catálogo de autores. |
| RF-10 | CRUD de géneros | El Administrador administra el catálogo de géneros. |
| RF-11 | CRUD de formatos | El Administrador administra el catálogo de formatos. |
| RF-12 | CRUD de categorías | El Administrador administra el catálogo de categorías. |
| RF-13 | CRUD de conceptos | El Administrador administra el catálogo de conceptos. |
| RF-14 | Autores múltiples | Un libro puede asociarse a varios autores y un autor a varios libros (tabla puente). |
| RF-15 | Géneros múltiples | Un libro puede pertenecer a varios géneros (tabla puente). |
| RF-16 | Conceptos por libro | Cada libro puede definir conceptos con definición propia, capítulo y página. El mismo concepto puede tener otra definición en otro libro. |
| RF-17 | Imágenes de libro | El Administrador carga JPG/PNG/WebP, edita texto alternativo, marca una portada y elimina imágenes. |
| RF-18 | Control de stock y precio | Precio ≥ 0 y stock ≥ 0; la BD rechaza valores inválidos. |
| RF-19 | Administración restringida | Solo el Administrador accede a CRUD y a usuarios. Un cliente recibe 403. |
| RF-20 | Administrador único | No es posible crear un segundo usuario con rol `admin`. |

## Requisitos no funcionales

| ID | Requisito | Criterio de aceptación |
| --- | --- | --- |
| RNF-01 | Seguridad | Secretos en `.env`; sesiones httpOnly; hash de contraseñas; SQL parametrizado; validación de uploads. |
| RNF-02 | Mantenibilidad | Separación app.js / config / routes / services / middleware / views. Las vistas no ejecutan SQL. |
| RNF-03 | Integridad de datos | PK, FK, UNIQUE, CHECK, índice de un admin, 4FN para M:N. |
| RNF-04 | Rendimiento básico | Índices en ISBN, título y FKs; pool de conexiones acotado. |
| RNF-05 | Usabilidad | Formularios HTML, mensajes de resultado y navegación coherente bajo `/library`. |
| RNF-06 | Disponibilidad del ejercicio | Proceso Node local + reverse proxy; falla del proxy no debe implicar abrir el puerto 3000 a Internet. |
| RNF-07 | Trazabilidad de errores | Errores se registran en servidor; el usuario ve mensajes genéricos. |
| RNF-08 | Despliegue | Documentado para CentOS Stream 10, PostgreSQL y Apache/NGINX. |

## Actores, operaciones y rechazos

### Visitante
- Puede: ver login y registro.
- No puede: catálogo, detalle, CRUD, administración.

### Usuario registrado (`client`)
- Puede: iniciar/cerrar sesión, ver catálogo, buscar, ver detalle y conceptos, ver su perfil.
- No puede: crear/editar/eliminar libros ni catálogos, ni cambiar roles. Recibe 403.

### Administrador (`admin`)
- Puede: todo lo del usuario registrado más CRUD de tablas administrables, imágenes, conceptos por libro y gestión de usuarios.
- No puede: crear un segundo administrador (la BD lo impide).

## Riesgos iniciales

1. Acceso no autorizado a rutas administrativas.
2. SQL Injection por concatenación de entrada de usuario.
3. Subida de archivos ejecutables o de tamaño excesivo.
4. Exposición de credenciales en git, evidencias o ubiquitous.
5. Eliminación accidental de libros o catálogos en uso.
6. Publicación de datos sensibles (hashes, `.env`, llaves SSH).
