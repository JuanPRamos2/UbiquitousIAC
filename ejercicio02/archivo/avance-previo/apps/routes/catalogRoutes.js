const express = require('express');
const router = express.Router();
const {
  listCategories,
  createCategory,
  updateCategory,
  deleteCategory,
  listFormats,
  createFormat,
  updateFormat,
  deleteFormat,
  listAuthors,
  createAuthor,
  updateAuthor,
  deleteAuthor,
  listGenres,
  createGenre,
  updateGenre,
  deleteGenre,
  listConcepts,
  createConcept,
  updateConcept,
  deleteConcept
} = require('../models/catalogModel');

const requireAdmin = (req, res, next) => {
  if (!req.session.user || req.session.user.role !== 'admin') {
    return res.status(403).render('error/403', { title: 'Acceso denegado' });
  }
  next();
};

router.use(requireAdmin);

router.get('/categories', async (req, res) => {
  const items = await listCategories();
  res.render('catalogs/categories', { title: 'Categorías', items });
});

router.post('/categories', async (req, res) => {
  await createCategory(req.body.name);
  res.redirect('/catalogs/categories');
});

router.post('/categories/:id/update', async (req, res) => {
  await updateCategory(req.params.id, req.body.name);
  res.redirect('/catalogs/categories');
});

router.post('/categories/:id/delete', async (req, res) => {
  await deleteCategory(req.params.id);
  res.redirect('/catalogs/categories');
});

router.get('/formats', async (req, res) => {
  const items = await listFormats();
  res.render('catalogs/formats', { title: 'Formatos', items });
});

router.post('/formats', async (req, res) => {
  await createFormat(req.body.name);
  res.redirect('/catalogs/formats');
});

router.post('/formats/:id/update', async (req, res) => {
  await updateFormat(req.params.id, req.body.name);
  res.redirect('/catalogs/formats');
});

router.post('/formats/:id/delete', async (req, res) => {
  await deleteFormat(req.params.id);
  res.redirect('/catalogs/formats');
});

router.get('/authors', async (req, res) => {
  const items = await listAuthors();
  res.render('catalogs/authors', { title: 'Autores', items });
});

router.post('/authors', async (req, res) => {
  await createAuthor(req.body.full_name);
  res.redirect('/catalogs/authors');
});

router.post('/authors/:id/update', async (req, res) => {
  await updateAuthor(req.params.id, req.body.full_name);
  res.redirect('/catalogs/authors');
});

router.post('/authors/:id/delete', async (req, res) => {
  await deleteAuthor(req.params.id);
  res.redirect('/catalogs/authors');
});

router.get('/genres', async (req, res) => {
  const items = await listGenres();
  res.render('catalogs/genres', { title: 'Géneros', items });
});

router.post('/genres', async (req, res) => {
  await createGenre(req.body.name);
  res.redirect('/catalogs/genres');
});

router.post('/genres/:id/update', async (req, res) => {
  await updateGenre(req.params.id, req.body.name);
  res.redirect('/catalogs/genres');
});

router.post('/genres/:id/delete', async (req, res) => {
  await deleteGenre(req.params.id);
  res.redirect('/catalogs/genres');
});

router.get('/concepts', async (req, res) => {
  const items = await listConcepts();
  res.render('catalogs/concepts', { title: 'Conceptos', items });
});

router.post('/concepts', async (req, res) => {
  await createConcept(req.body.name);
  res.redirect('/catalogs/concepts');
});

router.post('/concepts/:id/update', async (req, res) => {
  await updateConcept(req.params.id, req.body.name);
  res.redirect('/catalogs/concepts');
});

router.post('/concepts/:id/delete', async (req, res) => {
  await deleteConcept(req.params.id);
  res.redirect('/catalogs/concepts');
});

module.exports = router;
