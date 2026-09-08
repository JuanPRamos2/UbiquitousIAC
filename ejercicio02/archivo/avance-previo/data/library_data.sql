BEGIN;

-- Datos iniciales de catálogos
INSERT INTO formats (name, description) VALUES
    ('Tapa blanda', 'Edición impresa con cubierta flexible'),
    ('Tapa dura', 'Edición impresa con cubierta rígida'),
    ('Digital', 'Libro electrónico')
ON CONFLICT (name) DO NOTHING;

INSERT INTO categories (name, description) VALUES
    ('Literatura', 'Obras literarias y narrativa'),
    ('Tecnología', 'Programación e ingeniería de software'),
    ('Ciencias sociales', 'Sociedad, cultura e historia')
ON CONFLICT (name) DO NOTHING;

INSERT INTO authors (full_name, biography) VALUES
    ('Gabriel García Márquez', 'Escritor y periodista colombiano.'),
    ('Isabel Allende', 'Escritora chilena.'),
    ('Robert C. Martin', 'Autor y consultor de software.'),
    ('Yuval Noah Harari', 'Historiador y escritor israelí.')
ON CONFLICT (full_name) DO NOTHING;

INSERT INTO genres (name, description) VALUES
    ('Realismo mágico', 'Narrativa con elementos fantásticos integrados en la realidad.'),
    ('Novela', 'Obra narrativa extensa de ficción.'),
    ('Programación', 'Contenido centrado en desarrollo de software.'),
    ('Historia', 'Estudio y narración de hechos históricos.')
ON CONFLICT (name) DO NOTHING;

INSERT INTO concepts (name, description) VALUES
    ('Memoria', 'Facultad de conservar y recuperar experiencias.'),
    ('Identidad', 'Conjunto de rasgos que distingue a una persona o comunidad.'),
    ('Código limpio', 'Prácticas que favorecen código legible, mantenible y sencillo.'),
    ('Civilización', 'Sociedad humana con organización cultural y política compleja.')
ON CONFLICT (name) DO NOTHING;

-- Libros
INSERT INTO books (isbn, title, publication_year, price, stock, format_id, category_id, description)
SELECT '9780307474728', 'Cien años de soledad', 1967, 24.90, 12, f.id, c.id,
       'Novela sobre la familia Buendía y la historia de Macondo.'
FROM formats f, categories c
WHERE f.name = 'Tapa blanda' AND c.name = 'Literatura'
ON CONFLICT (isbn) DO NOTHING;

INSERT INTO books (isbn, title, publication_year, price, stock, format_id, category_id, description)
SELECT '9780132350884', 'Clean Code', 2008, 39.90, 8, f.id, c.id,
       'Guía práctica para escribir código legible y mantenible.'
FROM formats f, categories c
WHERE f.name = 'Tapa dura' AND c.name = 'Tecnología'
ON CONFLICT (isbn) DO NOTHING;

INSERT INTO books (isbn, title, publication_year, price, stock, format_id, category_id, description)
SELECT '9780062316097', 'Sapiens', 2011, 29.90, 10, f.id, c.id,
       'Recorrido por la historia de la humanidad.'
FROM formats f, categories c
WHERE f.name = 'Digital' AND c.name = 'Ciencias sociales'
ON CONFLICT (isbn) DO NOTHING;

-- Autores por libro
INSERT INTO book_authors (book_id, author_id)
SELECT b.id, a.id
FROM books b, authors a
WHERE b.isbn = '9780307474728' AND a.full_name = 'Gabriel García Márquez'
ON CONFLICT DO NOTHING;

INSERT INTO book_authors (book_id, author_id)
SELECT b.id, a.id
FROM books b, authors a
WHERE b.isbn = '9780132350884' AND a.full_name = 'Robert C. Martin'
ON CONFLICT DO NOTHING;

INSERT INTO book_authors (book_id, author_id)
SELECT b.id, a.id
FROM books b, authors a
WHERE b.isbn = '9780062316097' AND a.full_name = 'Yuval Noah Harari'
ON CONFLICT DO NOTHING;

-- Géneros por libro
INSERT INTO book_genres (book_id, genre_id)
SELECT b.id, g.id
FROM books b, genres g
WHERE b.isbn = '9780307474728' AND g.name IN ('Realismo mágico', 'Novela')
ON CONFLICT DO NOTHING;

INSERT INTO book_genres (book_id, genre_id)
SELECT b.id, g.id
FROM books b, genres g
WHERE b.isbn = '9780132350884' AND g.name = 'Programación'
ON CONFLICT DO NOTHING;

INSERT INTO book_genres (book_id, genre_id)
SELECT b.id, g.id
FROM books b, genres g
WHERE b.isbn = '9780062316097' AND g.name IN ('Historia', 'Novela')
ON CONFLICT DO NOTHING;

-- Definiciones específicas por libro
INSERT INTO book_concepts (book_id, concept_id, definition)
SELECT b.id, c.id, data.definition
FROM (VALUES
    ('9780307474728', 'Memoria', 'La memoria colectiva de Macondo conserva el pasado familiar y social.'),
    ('9780307474728', 'Identidad', 'La identidad de los Buendía se transforma a través de generaciones.'),
    ('9780132350884', 'Código limpio', 'Código expresivo, simple y fácil de mantener por otros desarrolladores.'),
    ('9780062316097', 'Civilización', 'Organización humana basada en cooperación, mitos compartidos e instituciones.')
) AS data(isbn, concept_name, definition)
JOIN books b ON b.isbn = data.isbn
JOIN concepts c ON c.name = data.concept_name
ON CONFLICT (book_id, concept_id) DO UPDATE
    SET definition = EXCLUDED.definition;

-- Imágenes de ejemplo. Sustituye estas URL por imágenes reales si es necesario.
INSERT INTO images (url, alt_text) VALUES
    ('https://images.example.com/cien-anos-de-soledad.jpg', 'Portada de Cien años de soledad'),
    ('https://images.example.com/clean-code.jpg', 'Portada de Clean Code'),
    ('https://images.example.com/sapiens.jpg', 'Portada de Sapiens')
ON CONFLICT (url) DO NOTHING;

INSERT INTO book_images (book_id, image_id)
SELECT b.id, i.id
FROM books b, images i
WHERE (b.isbn, i.url) IN (
    ('9780307474728', 'https://images.example.com/cien-anos-de-soledad.jpg'),
    ('9780132350884', 'https://images.example.com/clean-code.jpg'),
    ('9780062316097', 'https://images.example.com/sapiens.jpg')
)
ON CONFLICT DO NOTHING;

-- Los usuarios se registran desde la aplicación y no se modifican aquí.
COMMIT;
