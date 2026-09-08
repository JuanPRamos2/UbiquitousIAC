const { pool } = require('../config/db');

const listCategories = async () => {
  const result = await pool.query('SELECT * FROM categories ORDER BY name ASC');
  return result.rows;
};

const getCategory = async (id) => {
  const result = await pool.query('SELECT * FROM categories WHERE id = $1', [id]);
  return result.rows[0];
};

const createCategory = async (name) => {
  const result = await pool.query(
    'INSERT INTO categories (name) VALUES ($1) RETURNING *',
    [name]
  );
  return result.rows[0];
};

const updateCategory = async (id, name) => {
  const result = await pool.query(
    'UPDATE categories SET name = $1 WHERE id = $2 RETURNING *',
    [name, id]
  );
  return result.rows[0];
};

const deleteCategory = async (id) => {
  await pool.query('DELETE FROM categories WHERE id = $1', [id]);
};

const listFormats = async () => {
  const result = await pool.query('SELECT * FROM formats ORDER BY name ASC');
  return result.rows;
};

const getFormat = async (id) => {
  const result = await pool.query('SELECT * FROM formats WHERE id = $1', [id]);
  return result.rows[0];
};

const createFormat = async (name) => {
  const result = await pool.query('INSERT INTO formats (name) VALUES ($1) RETURNING *', [name]);
  return result.rows[0];
};

const updateFormat = async (id, name) => {
  const result = await pool.query('UPDATE formats SET name = $1 WHERE id = $2 RETURNING *', [name, id]);
  return result.rows[0];
};

const deleteFormat = async (id) => {
  await pool.query('DELETE FROM formats WHERE id = $1', [id]);
};

const listAuthors = async () => {
  const result = await pool.query('SELECT * FROM authors ORDER BY full_name ASC');
  return result.rows;
};

const getAuthor = async (id) => {
  const result = await pool.query('SELECT * FROM authors WHERE id = $1', [id]);
  return result.rows[0];
};

const createAuthor = async (fullName) => {
  const result = await pool.query(
    'INSERT INTO authors (full_name) VALUES ($1) RETURNING *',
    [fullName]
  );
  return result.rows[0];
};

const updateAuthor = async (id, fullName) => {
  const result = await pool.query(
    'UPDATE authors SET full_name = $1 WHERE id = $2 RETURNING *',
    [fullName, id]
  );
  return result.rows[0];
};

const deleteAuthor = async (id) => {
  await pool.query('DELETE FROM authors WHERE id = $1', [id]);
};

const listGenres = async () => {
  const result = await pool.query('SELECT * FROM genres ORDER BY name ASC');
  return result.rows;
};

const getGenre = async (id) => {
  const result = await pool.query('SELECT * FROM genres WHERE id = $1', [id]);
  return result.rows[0];
};

const createGenre = async (name) => {
  const result = await pool.query('INSERT INTO genres (name) VALUES ($1) RETURNING *', [name]);
  return result.rows[0];
};

const updateGenre = async (id, name) => {
  const result = await pool.query('UPDATE genres SET name = $1 WHERE id = $2 RETURNING *', [name, id]);
  return result.rows[0];
};

const deleteGenre = async (id) => {
  await pool.query('DELETE FROM genres WHERE id = $1', [id]);
};

const listConcepts = async () => {
  const result = await pool.query('SELECT * FROM concepts ORDER BY name ASC');
  return result.rows;
};

const getConcept = async (id) => {
  const result = await pool.query('SELECT * FROM concepts WHERE id = $1', [id]);
  return result.rows[0];
};

const createConcept = async (name) => {
  const result = await pool.query('INSERT INTO concepts (name) VALUES ($1) RETURNING *', [name]);
  return result.rows[0];
};

const updateConcept = async (id, name) => {
  const result = await pool.query('UPDATE concepts SET name = $1 WHERE id = $2 RETURNING *', [name, id]);
  return result.rows[0];
};

const deleteConcept = async (id) => {
  await pool.query('DELETE FROM concepts WHERE id = $1', [id]);
};

module.exports = {
  listCategories,
  getCategory,
  createCategory,
  updateCategory,
  deleteCategory,
  listFormats,
  getFormat,
  createFormat,
  updateFormat,
  deleteFormat,
  listAuthors,
  getAuthor,
  createAuthor,
  updateAuthor,
  deleteAuthor,
  listGenres,
  getGenre,
  createGenre,
  updateGenre,
  deleteGenre,
  listConcepts,
  getConcept,
  createConcept,
  updateConcept,
  deleteConcept
};
