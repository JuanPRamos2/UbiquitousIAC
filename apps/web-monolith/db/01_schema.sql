BEGIN;

CREATE TABLE formats (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE authors (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(200) NOT NULL UNIQUE,
    biography TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE genres (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE concepts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE books (
    id SERIAL PRIMARY KEY,
    isbn VARCHAR(17) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    publication_year SMALLINT NOT NULL CHECK (publication_year BETWEEN 1450 AND 2100),
    price NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    stock INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    format_id INTEGER NOT NULL REFERENCES formats(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE book_authors (
    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE ON UPDATE CASCADE,
    author_id INTEGER NOT NULL REFERENCES authors(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    PRIMARY KEY (book_id, author_id)
);

CREATE TABLE book_genres (
    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE ON UPDATE CASCADE,
    genre_id INTEGER NOT NULL REFERENCES genres(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    PRIMARY KEY (book_id, genre_id)
);

CREATE TABLE images (
    id SERIAL PRIMARY KEY,
    stored_name VARCHAR(255) NOT NULL UNIQUE,
    alt_text VARCHAR(255),
    mime_type VARCHAR(100) NOT NULL CHECK (mime_type IN ('image/jpeg', 'image/png', 'image/webp')),
    byte_size INTEGER NOT NULL CHECK (byte_size > 0 AND byte_size <= 5242880),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE book_images (
    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE ON UPDATE CASCADE,
    image_id INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE ON UPDATE CASCADE,
    is_cover BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (book_id, image_id)
);

CREATE TABLE book_concepts (
    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE ON UPDATE CASCADE,
    concept_id INTEGER NOT NULL REFERENCES concepts(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    definition TEXT NOT NULL CHECK (char_length(btrim(definition)) > 0),
    chapter VARCHAR(100),
    page_number INTEGER CHECK (page_number IS NULL OR page_number > 0),
    PRIMARY KEY (book_id, concept_id)
);

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'client' CHECK (role IN ('admin', 'client')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX ux_users_single_admin
    ON users (role)
    WHERE role = 'admin';

CREATE UNIQUE INDEX ux_book_images_one_cover
    ON book_images (book_id)
    WHERE is_cover;

CREATE INDEX idx_books_format_id ON books (format_id);
CREATE INDEX idx_books_category_id ON books (category_id);
CREATE INDEX idx_books_title ON books (title);
CREATE INDEX idx_books_isbn ON books (isbn);
CREATE INDEX idx_book_authors_author_id ON book_authors (author_id);
CREATE INDEX idx_book_genres_genre_id ON book_genres (genre_id);
CREATE INDEX idx_book_concepts_concept_id ON book_concepts (concept_id);
CREATE INDEX idx_users_email ON users (email);
CREATE INDEX idx_users_role ON users (role);

COMMIT;
