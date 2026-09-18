BEGIN;

CREATE OR REPLACE FUNCTION sp_search_books(p_isbn TEXT DEFAULT NULL, p_title TEXT DEFAULT NULL)
RETURNS TABLE (
    id INTEGER,
    isbn VARCHAR,
    title VARCHAR,
    publication_year SMALLINT,
    price NUMERIC,
    stock INTEGER,
    format_id INTEGER,
    category_id INTEGER,
    description TEXT,
    format_name VARCHAR,
    category_name VARCHAR
) AS $$
    SELECT b.id, b.isbn, b.title, b.publication_year, b.price, b.stock,
           b.format_id, b.category_id, b.description, f.name, c.name
    FROM books b
    JOIN formats f ON f.id = b.format_id
    JOIN categories c ON c.id = b.category_id
    WHERE (p_isbn IS NULL OR btrim(p_isbn) = '' OR b.isbn ILIKE '%' || btrim(p_isbn) || '%')
      AND (p_title IS NULL OR btrim(p_title) = '' OR b.title ILIKE '%' || btrim(p_title) || '%')
    ORDER BY b.title;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION sp_get_book(p_id INTEGER)
RETURNS TABLE (
    id INTEGER,
    isbn VARCHAR,
    title VARCHAR,
    publication_year SMALLINT,
    price NUMERIC,
    stock INTEGER,
    format_id INTEGER,
    category_id INTEGER,
    description TEXT,
    format_name VARCHAR,
    category_name VARCHAR
) AS $$
    SELECT b.id, b.isbn, b.title, b.publication_year, b.price, b.stock,
           b.format_id, b.category_id, b.description, f.name, c.name
    FROM books b
    JOIN formats f ON f.id = b.format_id
    JOIN categories c ON c.id = b.category_id
    WHERE b.id = p_id;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION sp_create_book(
    p_isbn TEXT,
    p_title TEXT,
    p_publication_year INTEGER,
    p_price NUMERIC,
    p_stock INTEGER,
    p_format_id INTEGER,
    p_category_id INTEGER,
    p_description TEXT
) RETURNS books AS $$
DECLARE
    rec books;
BEGIN
    INSERT INTO books (isbn, title, publication_year, price, stock, format_id, category_id, description)
    VALUES (btrim(p_isbn), btrim(p_title), p_publication_year, p_price, p_stock, p_format_id, p_category_id, p_description)
    RETURNING * INTO rec;
    RETURN rec;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_update_book(
    p_id INTEGER,
    p_isbn TEXT,
    p_title TEXT,
    p_publication_year INTEGER,
    p_price NUMERIC,
    p_stock INTEGER,
    p_format_id INTEGER,
    p_category_id INTEGER,
    p_description TEXT
) RETURNS books AS $$
DECLARE
    rec books;
BEGIN
    UPDATE books
       SET isbn = btrim(p_isbn),
           title = btrim(p_title),
           publication_year = p_publication_year,
           price = p_price,
           stock = p_stock,
           format_id = p_format_id,
           category_id = p_category_id,
           description = p_description
     WHERE id = p_id
     RETURNING * INTO rec;
    RETURN rec;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_delete_book(p_id INTEGER) RETURNS VOID AS $$
BEGIN
    DELETE FROM books WHERE id = p_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_set_book_authors(p_book_id INTEGER, p_author_ids INTEGER[])
RETURNS VOID AS $$
BEGIN
    DELETE FROM book_authors WHERE book_id = p_book_id;
    INSERT INTO book_authors (book_id, author_id)
    SELECT DISTINCT p_book_id, author_id
    FROM unnest(COALESCE(p_author_ids, ARRAY[]::INTEGER[])) AS author_id
    WHERE author_id IS NOT NULL;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_set_book_genres(p_book_id INTEGER, p_genre_ids INTEGER[])
RETURNS VOID AS $$
BEGIN
    DELETE FROM book_genres WHERE book_id = p_book_id;
    INSERT INTO book_genres (book_id, genre_id)
    SELECT DISTINCT p_book_id, genre_id
    FROM unnest(COALESCE(p_genre_ids, ARRAY[]::INTEGER[])) AS genre_id
    WHERE genre_id IS NOT NULL;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_upsert_book_concept(
    p_book_id INTEGER,
    p_concept_id INTEGER,
    p_definition TEXT,
    p_chapter TEXT,
    p_page_number INTEGER
) RETURNS book_concepts AS $$
DECLARE
    rec book_concepts;
BEGIN
    INSERT INTO book_concepts (book_id, concept_id, definition, chapter, page_number)
    VALUES (p_book_id, p_concept_id, btrim(p_definition), NULLIF(btrim(COALESCE(p_chapter, '')), ''), p_page_number)
    ON CONFLICT (book_id, concept_id) DO UPDATE
        SET definition = EXCLUDED.definition,
            chapter = EXCLUDED.chapter,
            page_number = EXCLUDED.page_number
    RETURNING * INTO rec;
    RETURN rec;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_delete_book_concept(p_book_id INTEGER, p_concept_id INTEGER)
RETURNS VOID AS $$
BEGIN
    DELETE FROM book_concepts WHERE book_id = p_book_id AND concept_id = p_concept_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_add_book_image(
    p_book_id INTEGER,
    p_stored_name TEXT,
    p_alt_text TEXT,
    p_mime_type TEXT,
    p_byte_size INTEGER,
    p_is_cover BOOLEAN
) RETURNS images AS $$
DECLARE
    rec images;
BEGIN
    INSERT INTO images (stored_name, alt_text, mime_type, byte_size)
    VALUES (p_stored_name, NULLIF(btrim(COALESCE(p_alt_text, '')), ''), p_mime_type, p_byte_size)
    RETURNING * INTO rec;

    IF p_is_cover THEN
        UPDATE book_images SET is_cover = FALSE WHERE book_id = p_book_id;
    END IF;

    INSERT INTO book_images (book_id, image_id, is_cover)
    VALUES (p_book_id, rec.id, COALESCE(p_is_cover, FALSE));

    RETURN rec;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_delete_book_image(p_book_id INTEGER, p_image_id INTEGER)
RETURNS TEXT AS $$
DECLARE
    fname TEXT;
BEGIN
    SELECT stored_name INTO fname FROM images WHERE id = p_image_id;
    DELETE FROM book_images WHERE book_id = p_book_id AND image_id = p_image_id;
    DELETE FROM images WHERE id = p_image_id;
    RETURN fname;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_set_cover(p_book_id INTEGER, p_image_id INTEGER)
RETURNS VOID AS $$
BEGIN
    UPDATE book_images SET is_cover = FALSE WHERE book_id = p_book_id;
    UPDATE book_images SET is_cover = TRUE
     WHERE book_id = p_book_id AND image_id = p_image_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_update_image_alt(p_image_id INTEGER, p_alt_text TEXT)
RETURNS VOID AS $$
BEGIN
    UPDATE images SET alt_text = NULLIF(btrim(COALESCE(p_alt_text, '')), '') WHERE id = p_image_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_create_user(
    p_full_name TEXT,
    p_email TEXT,
    p_password_hash TEXT,
    p_role TEXT
) RETURNS users AS $$
DECLARE
    rec users;
BEGIN
    INSERT INTO users (full_name, email, password_hash, role)
    VALUES (btrim(p_full_name), lower(btrim(p_email)), p_password_hash, COALESCE(p_role, 'client'))
    RETURNING * INTO rec;
    RETURN rec;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_update_user_role(p_id INTEGER, p_role TEXT)
RETURNS users AS $$
DECLARE
    rec users;
BEGIN
    UPDATE users SET role = p_role WHERE id = p_id RETURNING * INTO rec;
    RETURN rec;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_delete_user(p_id INTEGER) RETURNS VOID AS $$
BEGIN
    DELETE FROM users WHERE id = p_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_create_format(p_name TEXT, p_description TEXT)
RETURNS formats AS $$
DECLARE rec formats;
BEGIN
    INSERT INTO formats (name, description) VALUES (btrim(p_name), NULLIF(btrim(COALESCE(p_description, '')), ''))
    RETURNING * INTO rec;
    RETURN rec;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_update_format(p_id INTEGER, p_name TEXT, p_description TEXT)
RETURNS formats AS $$
DECLARE rec formats;
BEGIN
    UPDATE formats SET name = btrim(p_name), description = NULLIF(btrim(COALESCE(p_description, '')), '')
    WHERE id = p_id RETURNING * INTO rec;
    RETURN rec;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_delete_format(p_id INTEGER) RETURNS VOID AS $$
BEGIN
    DELETE FROM formats WHERE id = p_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_create_category(p_name TEXT, p_description TEXT)
RETURNS categories AS $$
DECLARE rec categories;
BEGIN
    INSERT INTO categories (name, description) VALUES (btrim(p_name), NULLIF(btrim(COALESCE(p_description, '')), ''))
    RETURNING * INTO rec;
    RETURN rec;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_update_category(p_id INTEGER, p_name TEXT, p_description TEXT)
RETURNS categories AS $$
DECLARE rec categories;
BEGIN
    UPDATE categories SET name = btrim(p_name), description = NULLIF(btrim(COALESCE(p_description, '')), '')
    WHERE id = p_id RETURNING * INTO rec;
    RETURN rec;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_delete_category(p_id INTEGER) RETURNS VOID AS $$
BEGIN
    DELETE FROM categories WHERE id = p_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_create_author(p_full_name TEXT, p_biography TEXT)
RETURNS authors AS $$
DECLARE rec authors;
BEGIN
    INSERT INTO authors (full_name, biography) VALUES (btrim(p_full_name), NULLIF(btrim(COALESCE(p_biography, '')), ''))
    RETURNING * INTO rec;
    RETURN rec;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_update_author(p_id INTEGER, p_full_name TEXT, p_biography TEXT)
RETURNS authors AS $$
DECLARE rec authors;
BEGIN
    UPDATE authors SET full_name = btrim(p_full_name), biography = NULLIF(btrim(COALESCE(p_biography, '')), '')
    WHERE id = p_id RETURNING * INTO rec;
    RETURN rec;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_delete_author(p_id INTEGER) RETURNS VOID AS $$
BEGIN
    DELETE FROM authors WHERE id = p_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_create_genre(p_name TEXT, p_description TEXT)
RETURNS genres AS $$
DECLARE rec genres;
BEGIN
    INSERT INTO genres (name, description) VALUES (btrim(p_name), NULLIF(btrim(COALESCE(p_description, '')), ''))
    RETURNING * INTO rec;
    RETURN rec;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_update_genre(p_id INTEGER, p_name TEXT, p_description TEXT)
RETURNS genres AS $$
DECLARE rec genres;
BEGIN
    UPDATE genres SET name = btrim(p_name), description = NULLIF(btrim(COALESCE(p_description, '')), '')
    WHERE id = p_id RETURNING * INTO rec;
    RETURN rec;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_delete_genre(p_id INTEGER) RETURNS VOID AS $$
BEGIN
    DELETE FROM genres WHERE id = p_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_create_concept(p_name TEXT, p_description TEXT)
RETURNS concepts AS $$
DECLARE rec concepts;
BEGIN
    INSERT INTO concepts (name, description) VALUES (btrim(p_name), NULLIF(btrim(COALESCE(p_description, '')), ''))
    RETURNING * INTO rec;
    RETURN rec;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_update_concept(p_id INTEGER, p_name TEXT, p_description TEXT)
RETURNS concepts AS $$
DECLARE rec concepts;
BEGIN
    UPDATE concepts SET name = btrim(p_name), description = NULLIF(btrim(COALESCE(p_description, '')), '')
    WHERE id = p_id RETURNING * INTO rec;
    RETURN rec;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_delete_concept(p_id INTEGER) RETURNS VOID AS $$
BEGIN
    DELETE FROM concepts WHERE id = p_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_dashboard_stats()
RETURNS TABLE (books INTEGER, categories INTEGER, authors INTEGER, users INTEGER) AS $$
    SELECT
        (SELECT COUNT(*)::int FROM books),
        (SELECT COUNT(*)::int FROM categories),
        (SELECT COUNT(*)::int FROM authors),
        (SELECT COUNT(*)::int FROM users);
$$ LANGUAGE sql STABLE;

COMMIT;
