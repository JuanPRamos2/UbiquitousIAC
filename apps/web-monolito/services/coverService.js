const fs = require('fs');
const path = require('path');
const { uploadDir } = require('../config/upload');

const CACHE_MS = 60 * 1000;
const FETCH_MS = 2500;

let catalogCache = { at: 0, byIsbn: new Map() };

const basePath = () => process.env.BASE_PATH || '/library';

const soapBase = () =>
  String(process.env.SOAP_URL || process.env.COVERS_API_URL || 'http://127.0.0.1:5001').replace(
    /\/+$/,
    ''
  );

const placeholderUrl = () => `${basePath()}/placeholder-book.svg`;

const openLibraryUrl = (isbn) =>
  `https://covers.openlibrary.org/b/isbn/${encodeURIComponent(isbn)}-L.jpg?default=false`;

const catalogCoverUrl = (isbn) => `${basePath()}/covers/${encodeURIComponent(isbn)}`;

const absoluteApiUrl = (value, isbn) => {
  if (value && /^https?:\/\//i.test(value)) return value;
  if (value) {
    return soapBase() + (value.startsWith('/') ? value : `/${value}`);
  }
  if (isbn) return `${soapBase()}/covers/${isbn}.svg`;
  return '';
};

const localUploadPath = (storedName) => {
  if (!storedName) return null;
  const filePath = path.join(uploadDir, storedName);
  return fs.existsSync(filePath) ? filePath : null;
};

const findSeedCoverFile = (isbn) => {
  const names = [`cover-${isbn}.png`, `cover-${isbn}.jpg`, `cover-${isbn}.jpeg`, `cover-${isbn}.webp`, `${isbn}.svg`];
  for (const name of names) {
    const filePath = path.join(uploadDir, name);
    if (fs.existsSync(filePath)) return filePath;
  }
  return null;
};

async function fetchCatalogImages() {
  if (Date.now() - catalogCache.at < CACHE_MS && catalogCache.byIsbn.size) {
    return catalogCache.byIsbn;
  }
  try {
    const response = await fetch(`${soapBase()}/books-images?format=json`, {
      headers: { Accept: 'application/json' },
      signal: AbortSignal.timeout(FETCH_MS)
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    const byIsbn = new Map();
    for (const book of payload.books || []) {
      byIsbn.set(String(book.isbn), {
        coverUrl: absoluteApiUrl(book.coverUrl, book.isbn),
        images: book.images || []
      });
    }
    catalogCache = { at: Date.now(), byIsbn };
  } catch (error) {
    if (!catalogCache.byIsbn.size) {
      console.warn('No se pudo leer /books-images del API Flask:', error.message);
    }
  }
  return catalogCache.byIsbn;
}

function decorateImage(book, image) {
  const local = localUploadPath(image.stored_name);
  return {
    ...image,
    url: local
      ? `${basePath()}/uploads/${image.stored_name}`
      : book.isbn
        ? catalogCoverUrl(book.isbn)
        : placeholderUrl(),
    is_local: Boolean(local)
  };
}

function coverFields(book, images) {
  const cover = (images || []).find((image) => image.is_cover) || (images || [])[0];
  return {
    cover_url: (cover && cover.url) || (book.isbn ? catalogCoverUrl(book.isbn) : placeholderUrl()),
    cover_fallback_url: book.isbn ? openLibraryUrl(book.isbn) : placeholderUrl()
  };
}

async function sendCover(isbn, res) {
  const safeIsbn = String(isbn || '').replace(/[^\dXx]/g, '');
  if (!safeIsbn) {
    res.redirect(placeholderUrl());
    return;
  }

  const local = findSeedCoverFile(safeIsbn);
  if (local) {
    res.sendFile(local);
    return;
  }

  const catalog = await fetchCatalogImages();
  const fromApi = catalog.get(safeIsbn);
  const candidates = [
    fromApi && fromApi.coverUrl,
    `${soapBase()}/covers/${safeIsbn}.svg`,
    `${soapBase()}/covers/cover-${safeIsbn}.png`
  ].filter(Boolean);

  for (const url of candidates) {
    try {
      const upstream = await fetch(url, { signal: AbortSignal.timeout(FETCH_MS) });
      if (!upstream.ok) continue;
      const contentType = upstream.headers.get('content-type') || 'image/svg+xml';
      const body = Buffer.from(await upstream.arrayBuffer());
      res.set('Content-Type', contentType);
      res.set('Cache-Control', 'public, max-age=86400');
      res.send(body);
      return;
    } catch (_error) {
      // Probar el siguiente origen del API.
    }
  }

  res.redirect(openLibraryUrl(safeIsbn));
}

module.exports = {
  fetchCatalogImages,
  decorateImage,
  coverFields,
  sendCover,
  placeholderUrl
};
