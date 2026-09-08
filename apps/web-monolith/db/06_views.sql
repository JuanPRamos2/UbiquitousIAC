BEGIN;

CREATE OR REPLACE VIEW v_book_catalog AS
SELECT
    b.id,
    b.isbn,
    b.title,
    b.publication_year,
    b.price,
    b.stock,
    f.name AS format_name,
    c.name AS category_name,
    (
        SELECT i.stored_name
        FROM book_images bi
        JOIN images i ON i.id = bi.image_id
        WHERE bi.book_id = b.id
        ORDER BY bi.is_cover DESC, i.id
        LIMIT 1
    ) AS cover_stored_name,
    (
        SELECT i.alt_text
        FROM book_images bi
        JOIN images i ON i.id = bi.image_id
        WHERE bi.book_id = b.id
        ORDER BY bi.is_cover DESC, i.id
        LIMIT 1
    ) AS cover_alt_text
FROM books b
JOIN formats f ON f.id = b.format_id
JOIN categories c ON c.id = b.category_id;

CREATE OR REPLACE VIEW v_book_authors AS
SELECT b.id AS book_id, b.isbn, b.title, a.id AS author_id, a.full_name
FROM books b
JOIN book_authors ba ON ba.book_id = b.id
JOIN authors a ON a.id = ba.author_id;

CREATE OR REPLACE VIEW v_book_genres AS
SELECT b.id AS book_id, b.isbn, b.title, g.id AS genre_id, g.name AS genre_name
FROM books b
JOIN book_genres bg ON bg.book_id = b.id
JOIN genres g ON g.id = bg.genre_id;

CREATE OR REPLACE VIEW v_book_concepts AS
SELECT b.id AS book_id, b.isbn, b.title,
       c.id AS concept_id, c.name AS concept_name,
       bc.definition, bc.chapter, bc.page_number
FROM books b
JOIN book_concepts bc ON bc.book_id = b.id
JOIN concepts c ON c.id = bc.concept_id;

CREATE OR REPLACE VIEW v_book_images AS
SELECT b.id AS book_id, b.isbn, b.title,
       i.id AS image_id, i.stored_name, i.alt_text, i.mime_type, i.byte_size, bi.is_cover
FROM books b
JOIN book_images bi ON bi.book_id = b.id
JOIN images i ON i.id = bi.image_id;

CREATE OR REPLACE VIEW v_low_stock AS
SELECT id, isbn, title, stock, price
FROM books
WHERE stock <= 3
ORDER BY stock ASC, title;

CREATE OR REPLACE VIEW v_admin_unique AS
SELECT COUNT(*)::int AS admin_count
FROM users
WHERE role = 'admin';

COMMIT;
