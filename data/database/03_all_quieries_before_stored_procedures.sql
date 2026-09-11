-- Consultas de verificación e integridad ANTES de depender de stored procedures.
-- El nombre conserva el del enunciado del ejercicio.
-- Ejecutar con: \i db/03_all_quieries_before_stored_procedures.sql

-- Conteos por tabla
SELECT 'formats' AS tabla, COUNT(*) FROM formats
UNION ALL SELECT 'categories', COUNT(*) FROM categories
UNION ALL SELECT 'authors', COUNT(*) FROM authors
UNION ALL SELECT 'genres', COUNT(*) FROM genres
UNION ALL SELECT 'concepts', COUNT(*) FROM concepts
UNION ALL SELECT 'books', COUNT(*) FROM books
UNION ALL SELECT 'images', COUNT(*) FROM images
UNION ALL SELECT 'users', COUNT(*) FROM users
UNION ALL SELECT 'book_authors', COUNT(*) FROM book_authors
UNION ALL SELECT 'book_genres', COUNT(*) FROM book_genres
UNION ALL SELECT 'book_concepts', COUNT(*) FROM book_concepts
UNION ALL SELECT 'book_images', COUNT(*) FROM book_images
ORDER BY 1;

-- Catálogo con autores y géneros (4FN: las M:N viven en tablas puente)
SELECT b.isbn, b.title, b.price, b.stock,
       string_agg(DISTINCT a.full_name, ', ' ORDER BY a.full_name) AS autores,
       string_agg(DISTINCT g.name, ', ' ORDER BY g.name) AS generos
FROM books b
LEFT JOIN book_authors ba ON ba.book_id = b.id
LEFT JOIN authors a ON a.id = ba.author_id
LEFT JOIN book_genres bg ON bg.book_id = b.id
LEFT JOIN genres g ON g.id = bg.genre_id
GROUP BY b.id
ORDER BY b.title;

-- Conceptos del libro de Cloud Computing (definición específica por libro)
SELECT b.title, c.name, bc.definition, bc.chapter, bc.page_number
FROM book_concepts bc
JOIN books b ON b.id = bc.book_id
JOIN concepts c ON c.id = bc.concept_id
WHERE b.isbn = '9780134444245'
ORDER BY c.name;

-- Búsqueda por ISBN y por título
SELECT isbn, title FROM books WHERE isbn = '9780134444245';
SELECT isbn, title FROM books WHERE title ILIKE '%cloud%';

-- Administrador único
SELECT id, email, role FROM users WHERE role = 'admin';

-- ============================================================
-- Pruebas negativas de integridad (se espera ERROR de PostgreSQL)
-- Conserve la sentencia, el resultado esperado y el error real.
-- ============================================================

-- ISBN duplicado. Esperado: 23505 unique_violation
-- ERROR: duplicate key value violates unique constraint "books_isbn_key"
-- INSERT INTO books (isbn, title, publication_year, price, stock, format_id, category_id)
-- SELECT '9780134444245', 'Duplicado', 2020, 10, 1, id, (SELECT id FROM categories LIMIT 1)
-- FROM formats LIMIT 1;

-- Stock negativo. Esperado: 23514 check_violation
-- INSERT INTO books (isbn, title, publication_year, price, stock, format_id, category_id)
-- SELECT '9780000000001', 'Stock inválido', 2020, 10, -1, f.id, c.id FROM formats f, categories c LIMIT 1;

-- Precio inválido. Esperado: 23514 check_violation
-- INSERT INTO books (isbn, title, publication_year, price, stock, format_id, category_id)
-- SELECT '9780000000002', 'Precio inválido', 2020, -5, 1, f.id, c.id FROM formats f, categories c LIMIT 1;

-- FK inexistente. Esperado: 23503 foreign_key_violation
-- INSERT INTO books (isbn, title, publication_year, price, stock, format_id, category_id)
-- VALUES ('9780000000003', 'FK inválida', 2020, 10, 1, 999999, 999999);

-- Eliminación que viola RESTRICT. Esperado: 23503 foreign_key_violation
-- DELETE FROM formats WHERE id IN (SELECT format_id FROM books LIMIT 1);

-- Segundo administrador. Esperado: unique index ux_users_single_admin o trigger
-- INSERT INTO users (full_name, email, password_hash, role)
-- VALUES ('Otro admin', 'otro-admin@library.local', 'hash', 'admin');
