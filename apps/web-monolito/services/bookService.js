const { query } = require('../config/db');

const attachRelations = async (books) => {
  if (!books.length) return books;
  const ids = books.map((book) => book.id);

  const [authors, genres, images, concepts] = await Promise.all([
    query('SELECT * FROM v_book_authors WHERE book_id = ANY($1) ORDER BY full_name', [ids]),
    query('SELECT * FROM v_book_genres WHERE book_id = ANY($1) ORDER BY genre_name', [ids]),
    query('SELECT * FROM v_book_images WHERE book_id = ANY($1) ORDER BY is_cover DESC, image_id', [ids]),
    query('SELECT * FROM v_book_concepts WHERE book_id = ANY($1) ORDER BY concept_name', [ids])
  ]);

  const group = (rows, key) =>
    rows.reduce((acc, row) => {
      acc[row.book_id] = acc[row.book_id] || [];
      acc[row.book_id].push(row);
      return acc;
    }, {});

  const authorsByBook = group(authors.rows);
  const genresByBook = group(genres.rows);
  const imagesByBook = group(images.rows);
  const conceptsByBook = group(concepts.rows);

  return books.map((book) => ({
    ...book,
    authors: authorsByBook[book.id] || [],
    genres: genresByBook[book.id] || [],
    images: imagesByBook[book.id] || [],
    concepts: conceptsByBook[book.id] || []
  }));
};

const searchBooks = async ({ isbn = '', title = '' } = {}) => {
  const result = await query('SELECT * FROM sp_search_books($1, $2)', [isbn || null, title || null]);
  return attachRelations(result.rows);
};

const getBookById = async (id) => {
  const result = await query('SELECT * FROM sp_get_book($1)', [id]);
  if (!result.rows[0]) return null;
  const [book] = await attachRelations(result.rows);
  return book;
};

const createBook = async (payload) => {
  const result = await query(
    'SELECT * FROM sp_create_book($1, $2, $3, $4, $5, $6, $7, $8)',
    [
      payload.isbn,
      payload.title,
      payload.publication_year,
      payload.price,
      payload.stock,
      payload.format_id,
      payload.category_id,
      payload.description || ''
    ]
  );
  return result.rows[0];
};

const updateBook = async (id, payload) => {
  const result = await query(
    'SELECT * FROM sp_update_book($1, $2, $3, $4, $5, $6, $7, $8, $9)',
    [
      id,
      payload.isbn,
      payload.title,
      payload.publication_year,
      payload.price,
      payload.stock,
      payload.format_id,
      payload.category_id,
      payload.description || ''
    ]
  );
  return result.rows[0];
};

const deleteBook = async (id) => {
  await query('SELECT sp_delete_book($1)', [id]);
};

const setBookAuthors = async (bookId, authorIds) => {
  await query('SELECT sp_set_book_authors($1, $2)', [bookId, authorIds]);
};

const setBookGenres = async (bookId, genreIds) => {
  await query('SELECT sp_set_book_genres($1, $2)', [bookId, genreIds]);
};

const upsertBookConcept = async (bookId, { concept_id, definition, chapter, page_number }) => {
  const result = await query(
    'SELECT * FROM sp_upsert_book_concept($1, $2, $3, $4, $5)',
    [bookId, concept_id, definition, chapter || null, page_number]
  );
  return result.rows[0];
};

const deleteBookConcept = async (bookId, conceptId) => {
  await query('SELECT sp_delete_book_concept($1, $2)', [bookId, conceptId]);
};

const getDashboardStats = async () => {
  try {
    const result = await query('SELECT * FROM sp_dashboard_stats()');
    if (result.rows[0]) return result.rows[0];
  } catch (_error) {
    // Si aún no existen los stored procedures, contar directo.
  }

  const [books, categories, authors, users] = await Promise.all([
    query('SELECT COUNT(*)::int AS count FROM books'),
    query('SELECT COUNT(*)::int AS count FROM categories'),
    query('SELECT COUNT(*)::int AS count FROM authors'),
    query('SELECT COUNT(*)::int AS count FROM users')
  ]);

  return {
    books: books.rows[0].count,
    categories: categories.rows[0].count,
    authors: authors.rows[0].count,
    users: users.rows[0].count
  };
};

module.exports = {
  searchBooks,
  getBookById,
  createBook,
  updateBook,
  deleteBook,
  setBookAuthors,
  setBookGenres,
  upsertBookConcept,
  deleteBookConcept,
  getDashboardStats
};
