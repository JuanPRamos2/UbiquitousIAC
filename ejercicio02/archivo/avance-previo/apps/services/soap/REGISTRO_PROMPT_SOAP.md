# Registro de archivos y carpetas de PROMPT_SOAP

## Ubicación base

`/home/bold/Documents/Integracion/library/apps/services/soap/`

## Archivos nuevos

| Elemento | Tipo | Propósito |
| --- | --- | --- |
| `services/soap/library.xml` | XML | Documento inicial de libros orientado al intercambio SOAP/XML. |
| `services/soap/library01.xml` | XML | Catálogo XML de libros con ISBN, título, autores, géneros, año, precio, stock, formato, imágenes y conceptos definidos por libro. |
| `services/soap/estilo.css` | CSS | Presentación visual profesional y responsiva de `library01.xml`. |
| `services/soap/REGISTRO_PROMPT_SOAP.md` | Markdown | Este inventario de archivos y cambios asociados al prompt. |

## Carpeta nueva

- `services/soap/`: contiene los documentos XML y la hoja de estilos del servicio de biblioteca.

## Archivo actualizado, no nuevo

- `apps/app.js`: publica la carpeta `services` mediante Express para permitir el acceso web a:
  - `http://localhost:3000/services/soap/library01.xml`
  - `http://localhost:3000/services/soap/estilo.css`

## Datos incluidos

`library01.xml` contiene los tres libros disponibles en PostgreSQL al momento de generar el documento:

- Cien años de soledad
- Clean Code
- Sapiens

Cada libro incluye sus relaciones de autores, géneros, imágenes y conceptos con sus definiciones.

## Validación

- El XML contiene una declaración XML válida.
- El XML referencia `estilo.css` mediante `xml-stylesheet`.
- El documento contiene 3 elementos `book`.
- Express entrega XML y CSS con respuesta HTTP `200`.
