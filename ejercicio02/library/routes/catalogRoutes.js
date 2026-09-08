const express = require('express');
const router = express.Router();
const { requireAdmin } = require('../middleware/auth');
const { setNotice, setError } = require('../middleware/flash');
const { friendlyDbError } = require('../services/dbErrors');
const catalogService = require('../services/catalogService');

router.use(requireAdmin);

const catalogs = [
  { slug: 'formats', title: 'Formatos', blurb: 'Tapa blanda, digital, audiolibro y demás presentaciones.', field: 'name', create: catalogService.createFormat, update: catalogService.updateFormat, remove: catalogService.deleteFormat, table: 'formats' },
  { slug: 'categories', title: 'Categorías', blurb: 'Temas generales para ordenar el acervo.', field: 'name', create: catalogService.createCategory, update: catalogService.updateCategory, remove: catalogService.deleteCategory, table: 'categories' },
  { slug: 'authors', title: 'Autores', blurb: 'Quienes escribieron o compilaron los libros.', field: 'full_name', extra: 'biography', create: catalogService.createAuthor, update: catalogService.updateAuthor, remove: catalogService.deleteAuthor, table: 'authors' },
  { slug: 'genres', title: 'Géneros', blurb: 'Novela, ensayo, programación y otros géneros.', field: 'name', create: catalogService.createGenre, update: catalogService.updateGenre, remove: catalogService.deleteGenre, table: 'genres' },
  { slug: 'concepts', title: 'Conceptos', blurb: 'Términos que luego se definen dentro de cada libro.', field: 'name', extra: 'description', create: catalogService.createConcept, update: catalogService.updateConcept, remove: catalogService.deleteConcept, table: 'concepts' }
];

function findCatalog(slug) {
  return catalogs.find((item) => item.slug === slug);
}

router.get('/', (req, res) => {
  res.render('catalogs/index', { title: 'Catálogos', catalogs });
});

router.get('/:slug', async (req, res, next) => {
  const catalog = findCatalog(req.params.slug);
  if (!catalog) return next();
  try {
    const items = await catalogService.list(catalog.table);
    res.render('catalogs/list', { title: catalog.title, catalog, items });
  } catch (error) {
    next(error);
  }
});

router.post('/:slug', async (req, res, next) => {
  const catalog = findCatalog(req.params.slug);
  if (!catalog) return next();
  try {
    const primary = (req.body[catalog.field] || '').trim();
    if (!primary) {
      setError(req, 'El nombre es obligatorio.');
    } else {
      await catalog.create(primary, req.body[catalog.extra] || req.body.description || '');
      setNotice(req, `${catalog.title.slice(0, -1)} creado.`);
    }
  } catch (error) {
    setError(req, friendlyDbError(error));
  }
  res.redirect(`${res.locals.basePath}/catalogs/${catalog.slug}`);
});

router.post('/:slug/:id/update', async (req, res, next) => {
  const catalog = findCatalog(req.params.slug);
  if (!catalog) return next();
  try {
    const primary = (req.body[catalog.field] || '').trim();
    if (!primary) {
      setError(req, 'El nombre es obligatorio.');
    } else {
      await catalog.update(req.params.id, primary, req.body[catalog.extra] || req.body.description || '');
      setNotice(req, 'Registro actualizado.');
    }
  } catch (error) {
    setError(req, friendlyDbError(error));
  }
  res.redirect(`${res.locals.basePath}/catalogs/${catalog.slug}`);
});

router.post('/:slug/:id/delete', async (req, res, next) => {
  const catalog = findCatalog(req.params.slug);
  if (!catalog) return next();
  try {
    await catalog.remove(req.params.id);
    setNotice(req, 'Registro eliminado.');
  } catch (error) {
    setError(req, friendlyDbError(error));
  }
  res.redirect(`${res.locals.basePath}/catalogs/${catalog.slug}`);
});

module.exports = router;
