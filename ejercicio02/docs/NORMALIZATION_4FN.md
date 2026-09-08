# Normalización hasta 4FN

El proceso tabular está en `docs/NORMALIZATION_4FN.xlsx`: **una sola hoja, de arriba hacia abajo**. Amarillo = PK. Verde = FK.

## 0FN (arriba de la hoja)

Una fila por libro. Autores, géneros, imágenes y conceptos van como listas en la misma celda.

`ISBN, Título, Año, Precio, Stock, Autores, Géneros, Formato, Categoría, Imágenes, Conceptos, Definiciones`

Viola 1FN: las celdas no son atómicas. La definición depende de (Libro, Concepto), no solo del concepto.

## 1FN (debajo)

Un valor por celda. El libro de Cloud Computing se copia 8 veces (2 autores × 2 géneros × 2 conceptos). Título, precio y stock se repiten. PK informal: `(ISBN, Autor, Género, Imagen, Concepto)`.

Viola 2FN: Título, Año, Precio, Stock, Formato y Categoría dependen solo de ISBN.

## 2FN

Se separa `LIBRO(ISBN, Título, Año, Precio, Stock, Formato, Categoría)`. El residuo sigue mezclando autor, género, imagen y concepto: el Cloud Computing sigue en 8 filas. Eso ya no es 2FN; es MVD.

## 3FN / BCNF

Formato y categoría (y el resto de catálogos) salen a tablas propias. `LIBRO` guarda `IdFormato` e `IdCategoria`. El residuo `(ISBN, IdAutor, IdGenero, IdImagen, IdConcepto, Definición…)` sigue en producto cartesiano.

## 4FN (abajo del todo)

MVD independientes:

- ISBN ↠ Autor → `book_authors`
- ISBN ↠ Género → `book_genres`
- ISBN ↠ Imagen → `book_images`
- ISBN ↠ Concepto → `book_concepts` (definición, capítulo, página)

Un administrador único no es una MVD; es cardinalidad sobre `users.role = 'admin'`.

## Productos

- Hoja de proceso: `docs/NORMALIZATION_4FN.xlsx`
- Diagrama del proceso (0FN→4FN, de arriba abajo): `img/NORMALIZATION_PROCESS.svg`
- Diagrama ER final: `img/DB_DESIGN_ER_4FN.svg`
- Esquema: `db/01_schema.sql`
