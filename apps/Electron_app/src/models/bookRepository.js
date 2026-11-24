import { getBooksUrl } from './configuration.js';

const text = (node, names) => {
  for (const name of names) {
    const match = node.querySelector(`:scope > ${name}`);
    if (match?.textContent?.trim()) return match.textContent.trim();
  }
  return '';
};

const values = (node, wrapperNames, itemNames) => {
  for (const wrapperName of wrapperNames) {
    const wrapper = node.querySelector(`:scope > ${wrapperName}`);
    if (wrapper) {
      return [...wrapper.querySelectorAll(itemNames.map((name) => `:scope > ${name}`).join(','))]
        .map((item) => item.textContent.trim())
        .filter(Boolean);
    }
  }
  return [];
};

const parseBook = (node) => ({
  isbn: text(node, ['isbn', 'ISBN']),
  title: text(node, ['title', 'name']) || 'Libro sin título',
  publicationYear: text(node, ['publicationYear', 'publication_year', 'year']) || 'Sin año',
  price: Number.parseFloat(text(node, ['price', 'precio'])) || 0,
  stock: Number.parseInt(text(node, ['stock', 'inventory']), 10) || 0,
  category: text(node, ['category', 'genre', 'genero']) || 'Sin género',
  coverUrl: text(node, ['coverUrl', 'coverURL', 'imageUrl', 'image', 'imagen']),
  authors: values(node, ['authors', 'authorList', 'autores'], ['author', 'authorName', 'name', 'autor']),
  genres: values(node, ['genres', 'genreList', 'generos'], ['genre', 'name', 'genero']),
});

export const fetchBooks = async (configuration, page, pageSize) => {
  const response = await fetch(getBooksUrl(configuration, page, pageSize), {
    headers: { Accept: 'application/xml, text/xml' },
  });
  if (!response.ok) throw new Error(`El servicio respondió con ${response.status}`);

  const xml = await response.text();
  const document = new DOMParser().parseFromString(xml, 'application/xml');
  const parserError = document.querySelector('parsererror');
  if (parserError) throw new Error('El servicio no devolvió XML válido');

  const books = [...document.querySelectorAll('books > book, catalog > book, response > book, book')]
    .map(parseBook);
  const count = Number.parseInt(text(document.documentElement, ['count', 'total']), 10);
  const serverIsPaginated = Number.isInteger(count) && books.length < count;
  const visibleBooks = serverIsPaginated ? books : books.slice((page - 1) * pageSize, page * pageSize);

  return {
    books: visibleBooks,
    total: Number.isInteger(count) ? count : books.length,
    requestedUrl: getBooksUrl(configuration, page, pageSize),
  };
};
