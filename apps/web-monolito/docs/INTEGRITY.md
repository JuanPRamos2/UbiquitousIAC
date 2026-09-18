# Integridad PostgreSQL

| Tabla | PK | FK | UNIQUE / CHECK relevantes | ON DELETE |
| --- | --- | --- | --- | --- |
| formats, categories, authors, genres, concepts | id | — | name UNIQUE | RESTRICT desde books/puentes |
| books | id | format_id, category_id | isbn UNIQUE; price≥0; stock≥0; año 1450–2100 | CASCADE a puentes del libro |
| book_authors | (book_id, author_id) | books, authors | — | libro CASCADE; autor RESTRICT |
| book_genres | (book_id, genre_id) | books, genres | — | igual |
| images | id | — | stored_name UNIQUE; MIME allowlist; tamaño ≤ 5 MB | — |
| book_images | (book_id, image_id) | books, images | un `is_cover` por libro | CASCADE |
| book_concepts | (book_id, concept_id) | books, concepts | definition no vacía; page>0 | libro CASCADE; concepto RESTRICT |
| users | id | — | email UNIQUE; role IN (admin, client); **un solo admin** | — |

**Un administrador:** índice único parcial `ux_users_single_admin` + trigger `fn_prevent_second_admin`. El índice impide dos filas `admin` aunque alguien eluda la aplicación. El trigger entrega un mensaje explícito.

Pruebas negativas documentadas en `db/03_all_quieries_before_stored_procedures.sql` y `TEST_PLAN.md` (T-19, T-21…T-25).
