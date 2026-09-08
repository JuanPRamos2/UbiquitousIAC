const { pool } = require('../config/db');

const getDashboardStats = async () => {
  const [books, categories, authors, users] = await Promise.all([
    pool.query('SELECT COUNT(*)::int AS count FROM books'),
    pool.query('SELECT COUNT(*)::int AS count FROM categories'),
    pool.query('SELECT COUNT(*)::int AS count FROM authors'),
    pool.query('SELECT COUNT(*)::int AS count FROM users')
  ]);

  return {
    books: books.rows[0].count,
    categories: categories.rows[0].count,
    authors: authors.rows[0].count,
    users: users.rows[0].count
  };
};

const listBooks = async () => {
  const result = await pool.query(`
    SELECT b.*, f.name AS format_name,
      json_agg(DISTINCT jsonb_build_object('id', a.id, 'full_name', a.full_name)) AS authors,
      json_agg(DISTINCT jsonb_build_object('id', g.id, 'name', g.name)) AS genres,
      json_agg(DISTINCT jsonb_build_object('id', i.id, 'url', i.url)) AS images,
      json_agg(DISTINCT jsonb_build_object('id', c.id, 'name', c.name, 'definition', bc.definition)) AS concepts
    FROM books b
    LEFT JOIN formats f ON f.id = b.format_id
    LEFT JOIN book_authors ba ON ba.book_id = b.id
    LEFT JOIN authors a ON a.id = ba.author_id
    LEFT JOIN book_genres bg ON bg.book_id = b.id
    LEFT JOIN genres g ON g.id = bg.genre_id
    LEFT JOIN book_images bi ON bi.book_id = b.id
    LEFT JOIN images i ON i.id = bi.image_id
    LEFT JOIN book_concepts bc ON bc.book_id = b.id
    LEFT JOIN concepts c ON c.id = bc.concept_id
    GROUP BY b.id, f.name
    ORDER BY b.title ASC
  `);

  return result.rows.map((book) => ({
    ...book,
    authors: book.authors || [],
    genres: book.genres || [],
    images: book.images || [],
    concepts: book.concepts || []
  }));
};

const getBookById = async (id) => {
  const result = await pool.query(`
    SELECT b.*, f.name AS format_name,
      COALESCE(
        json_agg(DISTINCT jsonb_build_object('id', a.id, 'full_name', a.full_name)) FILTER (WHERE a.id IS NOT NULL),
        '[]'::json
      ) AS authors,
      COALESCE(
        json_agg(DISTINCT jsonb_build_object('id', g.id, 'name', g.name)) FILTER (WHERE g.id IS NOT NULL),
        '[]'::json
      ) AS genres,
      COALESCE(
        json_agg(DISTINCT jsonb_build_object('id', i.id, 'url', i.url)) FILTER (WHERE i.id IS NOT NULL),
        '[]'::json
      ) AS images,
      COALESCE(
        json_agg(DISTINCT jsonb_build_object('id', c.id, 'name', c.name, 'definition', bc.definition)) FILTER (WHERE c.id IS NOT NULL),
        '[]'::json
      ) AS concepts
    FROM books b
    LEFT JOIN formats f ON f.id = b.format_id
    LEFT JOIN book_authors ba ON ba.book_id = b.id
    LEFT JOIN authors a ON a.id = ba.author_id
    LEFT JOIN book_genres bg ON bg.book_id = b.id
    LEFT JOIN genres g ON g.id = bg.genre_id
    LEFT JOIN book_images bi ON bi.book_id = b.id
    LEFT JOIN images i ON i.id = bi.image_id
    LEFT JOIN book_concepts bc ON bc.book_id = b.id
    LEFT JOIN concepts c ON c.id = bc.concept_id
    WHERE b.id = $1
    GROUP BY b.id, f.name
  `, [id]);

  if (!result.rows[0]) return null;

  const book = result.rows[0];
  return {
    ...book,
    authors: book.authors || [],
    genres: book.genres || [],
    images: book.images || [],
    concepts: book.concepts || []
  };
};

const createBook = async ({ isbn, title, publication_year, price, stock, format_id, category_id, description }) => {
  const result = await pool.query(
    `INSERT INTO books (isbn, title, publication_year, price, stock, format_id, category_id, description)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
     RETURNING *`,
    [isbn, title, publication_year, price, stock, format_id, category_id, description]
  );
  return result.rows[0];
};

const updateBook = async (id, fields) => {
  const entries = Object.entries(fields).filter(([, value]) => value !== undefined && value !== null);
  if (entries.length === 0) return await getBookById(id);

  const setClauses = entries.map(([key], index) => `${key} = $${index + 2}`).join(', ');
  const values = entries.map(([, value]) => value);
  const result = await pool.query(
    `UPDATE books SET ${setClauses} WHERE id = $1 RETURNING *`,
    [id, ...values]
  );
  return result.rows[0];
};

const deleteBook = async (id) => {
  await pool.query('DELETE FROM books WHERE id = $1', [id]);
};

const addAuthorToBook = async (bookId, authorId) => {
  await pool.query(
    'INSERT INTO book_authors (book_id, author_id) VALUES ($1, $2) ON CONFLICT DO NOTHING',
    [bookId, authorId]
  );
};

const removeAuthorFromBook = async (bookId, authorId) => {
  await pool.query('DELETE FROM book_authors WHERE book_id = $1 AND author_id = $2', [bookId, authorId]);
};

const setBookAuthors = async (bookId, authorIds) => {
  await pool.query('DELETE FROM book_authors WHERE book_id = $1', [bookId]);
  for (const authorId of authorIds) {
    await pool.query('INSERT INTO book_authors (book_id, author_id) VALUES ($1, $2)', [bookId, authorId]);
  }
};

const addGenreToBook = async (bookId, genreId) => {
  await pool.query(
    'INSERT INTO book_genres (book_id, genre_id) VALUES ($1, $2) ON CONFLICT DO NOTHING',
    [bookId, genreId]
  );
};

const setBookGenres = async (bookId, genreIds) => {
  await pool.query('DELETE FROM book_genres WHERE book_id = $1', [bookId]);
  for (const genreId of genreIds) {
    await pool.query('INSERT INTO book_genres (book_id, genre_id) VALUES ($1, $2)', [bookId, genreId]);
  }
};

const addConceptToBook = async (bookId, conceptId, definition) => {
  await pool.query(
    `INSERT INTO book_concepts (book_id, concept_id, definition) VALUES ($1, $2, $3)
     ON CONFLICT (book_id, concept_id) DO UPDATE SET definition = EXCLUDED.definition`,
    [bookId, conceptId, definition]
  );
};

const setBookConcepts = async (bookId, concepts) => {
  await pool.query('DELETE FROM book_concepts WHERE book_id = $1', [bookId]);
  for (const item of concepts) {
    await pool.query(
      'INSERT INTO book_concepts (book_id, concept_id, definition) VALUES ($1, $2, $3)',
      [bookId, item.concept_id, item.definition]
    );
  }
};

const addImageToBook = async (bookId, imageUrl) => {
  const image = await pool.query(
    'INSERT INTO images (url) VALUES ($1) RETURNING *',
    [imageUrl]
  );
  await pool.query('INSERT INTO book_images (book_id, image_id) VALUES ($1, $2)', [bookId, image.id]);
  return image.rows[0];
};

const deleteImageFromBook = async (bookId, imageId) => {
  await pool.query('DELETE FROM book_images WHERE book_id = $1 AND image_id = $2', [bookId, imageId]);
  await pool.query('DELETE FROM images WHERE id = $1', [imageId]);
};

const getBookConcepts = async (bookId) => {
  const result = await pool.query(
    `SELECT bc.definition, c.id, c.name FROM book_concepts bc
     JOIN concepts c ON c.id = bc.concept_id
     WHERE bc.book_id = $1`,
    [bookId]
  );
  return result.rows;
};

module.exports = {
  getDashboardStats,
  listBooks,
  getBookById,
  createBook,
  updateBook,
  deleteBook,
  addAuthorToBook,
  removeAuthorFromBook,
  setBookAuthors,
  addGenreToBook,
  setBookGenres,
  addConceptToBook,
  setBookConcepts,
  addImageToBook,
  deleteImageFromBook,
  getBookConcepts
};
