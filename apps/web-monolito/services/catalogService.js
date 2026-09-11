const { query } = require('../config/db');

const list = async (table, orderBy) => {
  const allowed = {
    formats: 'name',
    categories: 'name',
    authors: 'full_name',
    genres: 'name',
    concepts: 'name'
  };
  if (!allowed[table]) throw new Error('Catálogo no permitido');
  const result = await query(`SELECT * FROM ${table} ORDER BY ${allowed[table]} ASC`);
  return result.rows;
};

const createFormat = (name, description) =>
  query('SELECT * FROM sp_create_format($1, $2)', [name, description || '']).then((r) => r.rows[0]);
const updateFormat = (id, name, description) =>
  query('SELECT * FROM sp_update_format($1, $2, $3)', [id, name, description || '']).then((r) => r.rows[0]);
const deleteFormat = (id) => query('SELECT sp_delete_format($1)', [id]);

const createCategory = (name, description) =>
  query('SELECT * FROM sp_create_category($1, $2)', [name, description || '']).then((r) => r.rows[0]);
const updateCategory = (id, name, description) =>
  query('SELECT * FROM sp_update_category($1, $2, $3)', [id, name, description || '']).then((r) => r.rows[0]);
const deleteCategory = (id) => query('SELECT sp_delete_category($1)', [id]);

const createAuthor = (fullName, biography) =>
  query('SELECT * FROM sp_create_author($1, $2)', [fullName, biography || '']).then((r) => r.rows[0]);
const updateAuthor = (id, fullName, biography) =>
  query('SELECT * FROM sp_update_author($1, $2, $3)', [id, fullName, biography || '']).then((r) => r.rows[0]);
const deleteAuthor = (id) => query('SELECT sp_delete_author($1)', [id]);

const createGenre = (name, description) =>
  query('SELECT * FROM sp_create_genre($1, $2)', [name, description || '']).then((r) => r.rows[0]);
const updateGenre = (id, name, description) =>
  query('SELECT * FROM sp_update_genre($1, $2, $3)', [id, name, description || '']).then((r) => r.rows[0]);
const deleteGenre = (id) => query('SELECT sp_delete_genre($1)', [id]);

const createConcept = (name, description) =>
  query('SELECT * FROM sp_create_concept($1, $2)', [name, description || '']).then((r) => r.rows[0]);
const updateConcept = (id, name, description) =>
  query('SELECT * FROM sp_update_concept($1, $2, $3)', [id, name, description || '']).then((r) => r.rows[0]);
const deleteConcept = (id) => query('SELECT sp_delete_concept($1)', [id]);

module.exports = {
  list,
  createFormat,
  updateFormat,
  deleteFormat,
  createCategory,
  updateCategory,
  deleteCategory,
  createAuthor,
  updateAuthor,
  deleteAuthor,
  createGenre,
  updateGenre,
  deleteGenre,
  createConcept,
  updateConcept,
  deleteConcept
};
