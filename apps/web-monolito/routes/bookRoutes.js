const express = require('express');
const router = express.Router();
const { upload } = require('../config/upload');
const { requireAuth, requireAdmin } = require('../middleware/auth');
const { asArray, toInt, toNumber, validateBookPayload } = require('../middleware/validate');
const { setNotice, setError } = require('../middleware/flash');
const { friendlyDbError } = require('../services/dbErrors');
const bookService = require('../services/bookService');
const imageService = require('../services/imageService');
const catalogService = require('../services/catalogService');

const loadFormCatalogs = async () => {
  const [categories, formats, authors, genres, concepts] = await Promise.all([
    catalogService.list('categories'),
    catalogService.list('formats'),
    catalogService.list('authors'),
    catalogService.list('genres'),
    catalogService.list('concepts')
  ]);
  return { categories, formats, authors, genres, concepts };
};

const applyRelations = async (bookId, body) => {
  const authorIds = asArray(body.author_ids).map(toInt).filter(Boolean);
  const genreIds = asArray(body.genre_ids).map(toInt).filter(Boolean);
  await bookService.setBookAuthors(bookId, authorIds);
  await bookService.setBookGenres(bookId, genreIds);
};

const saveUploadedImages = async (bookId, files, body) => {
  if (!files || !files.length) return;
  const altTexts = asArray(body.image_alt);
  for (const [index, file] of files.entries()) {
    await imageService.addImage(bookId, file, {
      altText: altTexts[index] || body.image_alt || '',
      isCover: String(body.cover_index) === String(index)
    });
  }
};

router.use(requireAuth);

router.get('/', async (req, res, next) => {
  try {
    const books = await bookService.searchBooks({
      isbn: req.query.isbn || '',
      title: req.query.title || ''
    });
    res.render('books/index', {
      title: 'Catálogo',
      books,
      isbn: req.query.isbn || '',
      titleQuery: req.query.title || ''
    });
  } catch (error) {
    next(error);
  }
});

router.get('/new', requireAdmin, async (req, res, next) => {
  try {
    const catalogs = await loadFormCatalogs();
    res.render('books/new', { title: 'Nuevo libro', error: null, book: {}, ...catalogs });
  } catch (error) {
    next(error);
  }
});

router.post('/', requireAdmin, upload.array('images', 5), async (req, res, next) => {
  try {
    const errors = validateBookPayload(req.body);
    if (errors.length) {
      const catalogs = await loadFormCatalogs();
      return res.status(400).render('books/new', {
        title: 'Nuevo libro',
        error: errors.join(' '),
        book: req.body,
        ...catalogs
      });
    }

    const book = await bookService.createBook({
      isbn: req.body.isbn.trim(),
      title: req.body.title.trim(),
      publication_year: toInt(req.body.publication_year),
      price: toNumber(req.body.price),
      stock: toInt(req.body.stock),
      format_id: toInt(req.body.format_id),
      category_id: toInt(req.body.category_id),
      description: req.body.description || ''
    });

    await applyRelations(book.id, req.body);
    await saveUploadedImages(book.id, req.files, req.body);
    setNotice(req, 'Libro creado.');
    res.redirect(`${res.locals.basePath}/books/${book.id}`);
  } catch (error) {
    const catalogs = await loadFormCatalogs();
    res.status(400).render('books/new', {
      title: 'Nuevo libro',
      error: friendlyDbError(error),
      book: req.body,
      ...catalogs
    });
  }
});

router.get('/:id', async (req, res, next) => {
  try {
    const book = await bookService.getBookById(req.params.id);
    if (!book) return res.status(404).render('error/404', { title: 'Libro no encontrado' });
    res.render('books/show', { title: book.title, book });
  } catch (error) {
    next(error);
  }
});

router.get('/:id/edit', requireAdmin, async (req, res, next) => {
  try {
    const book = await bookService.getBookById(req.params.id);
    if (!book) return res.status(404).render('error/404', { title: 'Libro no encontrado' });
    const catalogs = await loadFormCatalogs();
    res.render('books/edit', { title: `Editar ${book.title}`, book, error: null, ...catalogs });
  } catch (error) {
    next(error);
  }
});

router.post('/:id', requireAdmin, upload.array('images', 5), async (req, res, next) => {
  try {
    const errors = validateBookPayload(req.body);
    if (errors.length) {
      const book = await bookService.getBookById(req.params.id);
      const catalogs = await loadFormCatalogs();
      return res.status(400).render('books/edit', {
        title: `Editar ${book ? book.title : 'libro'}`,
        book: { ...book, ...req.body },
        error: errors.join(' '),
        ...catalogs
      });
    }

    await bookService.updateBook(req.params.id, {
      isbn: req.body.isbn.trim(),
      title: req.body.title.trim(),
      publication_year: toInt(req.body.publication_year),
      price: toNumber(req.body.price),
      stock: toInt(req.body.stock),
      format_id: toInt(req.body.format_id),
      category_id: toInt(req.body.category_id),
      description: req.body.description || ''
    });
    await applyRelations(req.params.id, req.body);
    await saveUploadedImages(req.params.id, req.files, req.body);
    setNotice(req, 'Libro actualizado.');
    res.redirect(`${res.locals.basePath}/books/${req.params.id}`);
  } catch (error) {
    setError(req, friendlyDbError(error));
    res.redirect(`${res.locals.basePath}/books/${req.params.id}/edit`);
  }
});

router.post('/:id/delete', requireAdmin, async (req, res) => {
  try {
    await bookService.deleteBook(req.params.id);
    setNotice(req, 'Libro eliminado.');
    res.redirect(`${res.locals.basePath}/books`);
  } catch (error) {
    setError(req, friendlyDbError(error));
    res.redirect(`${res.locals.basePath}/books/${req.params.id}`);
  }
});

router.get('/:id/concepts', requireAdmin, async (req, res, next) => {
  try {
    const book = await bookService.getBookById(req.params.id);
    if (!book) return res.status(404).render('error/404', { title: 'Libro no encontrado' });
    const concepts = await catalogService.list('concepts');
    res.render('books/concepts', { title: `Conceptos de ${book.title}`, book, concepts });
  } catch (error) {
    next(error);
  }
});

router.post('/:id/concepts', requireAdmin, async (req, res) => {
  try {
    const definition = (req.body.definition || '').trim();
    if (!definition || !toInt(req.body.concept_id)) {
      setError(req, 'Seleccione un concepto y escriba una definición.');
    } else {
      await bookService.upsertBookConcept(req.params.id, {
        concept_id: toInt(req.body.concept_id),
        definition,
        chapter: req.body.chapter || '',
        page_number: toInt(req.body.page_number)
      });
      setNotice(req, 'Definición guardada.');
    }
  } catch (error) {
    setError(req, friendlyDbError(error));
  }
  res.redirect(`${res.locals.basePath}/books/${req.params.id}/concepts`);
});

router.post('/:id/concepts/:conceptId/delete', requireAdmin, async (req, res) => {
  try {
    await bookService.deleteBookConcept(req.params.id, req.params.conceptId);
    setNotice(req, 'Definición eliminada.');
  } catch (error) {
    setError(req, friendlyDbError(error));
  }
  res.redirect(`${res.locals.basePath}/books/${req.params.id}/concepts`);
});

router.post('/:id/images/delete', requireAdmin, async (req, res) => {
  try {
    await imageService.deleteImage(req.params.id, req.body.image_id);
    setNotice(req, 'Imagen eliminada.');
  } catch (error) {
    setError(req, friendlyDbError(error));
  }
  res.redirect(`${res.locals.basePath}/books/${req.params.id}`);
});

router.post('/:id/images/cover', requireAdmin, async (req, res) => {
  try {
    await imageService.setCover(req.params.id, req.body.image_id);
    if (req.body.alt_text !== undefined) {
      await imageService.updateAlt(req.body.image_id, req.body.alt_text);
    }
    setNotice(req, 'Portada actualizada.');
  } catch (error) {
    setError(req, friendlyDbError(error));
  }
  res.redirect(`${res.locals.basePath}/books/${req.params.id}`);
});

router.post('/:id/images/alt', requireAdmin, async (req, res) => {
  try {
    await imageService.updateAlt(req.body.image_id, req.body.alt_text);
    setNotice(req, 'Texto alternativo actualizado.');
  } catch (error) {
    setError(req, friendlyDbError(error));
  }
  res.redirect(`${res.locals.basePath}/books/${req.params.id}`);
});

module.exports = router;
