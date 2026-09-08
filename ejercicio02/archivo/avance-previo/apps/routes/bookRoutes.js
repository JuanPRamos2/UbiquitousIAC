const express = require('express');
const router = express.Router();
const upload = require('../config/upload');
const {
  listBooks,
  getBookById,
  createBook,
  updateBook,
  deleteBook,
  setBookAuthors,
  setBookGenres,
  setBookConcepts,
  addImageToBook,
  deleteImageFromBook,
  getBookConcepts
} = require('../models/bookModel');
const { listCategories, listFormats, listAuthors, listGenres, listConcepts } = require('../models/catalogModel');

const requireAuth = (req, res, next) => {
  if (!req.session.user) return res.redirect('/login');
  next();
};

router.use(requireAuth);

router.get('/', async (req, res) => {
  const books = await listBooks();
  res.render('books/index', { title: 'Catálogo', books });
});

router.get('/new', async (req, res) => {
  const [categories, formats, authors, genres, concepts] = await Promise.all([
    listCategories(),
    listFormats(),
    listAuthors(),
    listGenres(),
    listConcepts()
  ]);

  res.render('books/new', {
    title: 'Nuevo libro',
    categories,
    formats,
    authors,
    genres,
    concepts,
    error: null
  });
});

router.post('/', upload.array('images', 5), async (req, res) => {
  try {
    const { isbn, title, publication_year, price, stock, format_id, category_id, author_ids, genre_ids, concept_ids, concept_definitions } = req.body;

    const book = await createBook({
      isbn,
      title,
      publication_year: Number(publication_year),
      price: Number(price),
      stock: Number(stock),
      format_id: Number(format_id),
      category_id: Number(category_id),
      description: req.body.description || ''
    });

    const authorIds = Array.isArray(author_ids) ? author_ids : [author_ids].filter(Boolean);
    const genreIds = Array.isArray(genre_ids) ? genre_ids : [genre_ids].filter(Boolean);
    const conceptIds = Array.isArray(concept_ids) ? concept_ids : [concept_ids].filter(Boolean);
    const conceptDefinitions = Array.isArray(concept_definitions) ? concept_definitions : [concept_definitions].filter(Boolean);

    if (authorIds.length) await setBookAuthors(book.id, authorIds.map(Number));
    if (genreIds.length) await setBookGenres(book.id, genreIds.map(Number));

    const concepts = conceptIds.map((conceptId, index) => ({
      concept_id: Number(conceptId),
      definition: conceptDefinitions[index] || ''
    })).filter(item => item.concept_id);

    if (concepts.length) await setBookConcepts(book.id, concepts);

    if (req.files && req.files.length) {
      for (const file of req.files) {
        await addImageToBook(book.id, `/uploads/${file.filename}`);
      }
    }

    res.redirect('/books');
  } catch (error) {
    console.error(error);
    const [categories, formats, authors, genres, concepts] = await Promise.all([
      listCategories(),
      listFormats(),
      listAuthors(),
      listGenres(),
      listConcepts()
    ]);

    res.status(400).render('books/new', {
      title: 'Nuevo libro',
      categories,
      formats,
      authors,
      genres,
      concepts,
      error: 'No se pudo guardar el libro. Revisa los datos.'
    });
  }
});

router.get('/:id', async (req, res) => {
  const book = await getBookById(req.params.id);
  if (!book) return res.status(404).render('error/404', { title: 'Libro no encontrado' });

  const bookConcepts = await getBookConcepts(book.id);
  res.render('books/show', { title: book.title, book, concepts: bookConcepts });
});

router.get('/:id/edit', async (req, res) => {
  const book = await getBookById(req.params.id);
  if (!book) return res.status(404).render('error/404', { title: 'Libro no encontrado' });

  const [categories, formats, authors, genres, concepts] = await Promise.all([
    listCategories(),
    listFormats(),
    listAuthors(),
    listGenres(),
    listConcepts()
  ]);

  res.render('books/edit', {
    title: `Editar ${book.title}`,
    book,
    categories,
    formats,
    authors,
    genres,
    concepts,
    error: null
  });
});

router.put('/:id', upload.array('images', 5), async (req, res) => {
  try {
    const bookId = req.params.id;
    const update = {
      isbn: req.body.isbn,
      title: req.body.title,
      publication_year: Number(req.body.publication_year),
      price: Number(req.body.price),
      stock: Number(req.body.stock),
      format_id: Number(req.body.format_id),
      category_id: Number(req.body.category_id),
      description: req.body.description || ''
    };

    await updateBook(bookId, update);

    const authorIds = Array.isArray(req.body.author_ids) ? req.body.author_ids : [req.body.author_ids].filter(Boolean);
    const genreIds = Array.isArray(req.body.genre_ids) ? req.body.genre_ids : [req.body.genre_ids].filter(Boolean);
    const conceptIds = Array.isArray(req.body.concept_ids) ? req.body.concept_ids : [req.body.concept_ids].filter(Boolean);
    const conceptDefinitions = Array.isArray(req.body.concept_definitions) ? req.body.concept_definitions : [req.body.concept_definitions].filter(Boolean);

    if (authorIds.length) await setBookAuthors(bookId, authorIds.map(Number));
    if (genreIds.length) await setBookGenres(bookId, genreIds.map(Number));

    const concepts = conceptIds.map((conceptId, index) => ({
      concept_id: Number(conceptId),
      definition: conceptDefinitions[index] || ''
    })).filter(item => item.concept_id);

    if (concepts.length) await setBookConcepts(bookId, concepts);

    if (req.files && req.files.length) {
      for (const file of req.files) {
        await addImageToBook(bookId, `/uploads/${file.filename}`);
      }
    }

    res.redirect(`/books/${bookId}`);
  } catch (error) {
    console.error(error);
    res.redirect(`/books/${req.params.id}/edit`);
  }
});

router.post('/:id/delete', async (req, res) => {
  await deleteBook(req.params.id);
  res.redirect('/books');
});

router.post('/:id/images/delete', async (req, res) => {
  await deleteImageFromBook(req.params.id, req.body.image_id);
  res.redirect(`/books/${req.params.id}`);
});

module.exports = router;
