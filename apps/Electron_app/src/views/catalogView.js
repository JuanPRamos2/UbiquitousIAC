const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
const placeholder = (title) => `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="320" height="420" viewBox="0 0 320 420"><rect width="320" height="420" fill="#d9d1c3"/><path d="M40 48h240v324H40z" fill="#f5f1ea"/><path d="M64 88h192M64 112h142M64 304h192" stroke="#bb6b4b" stroke-width="8"/><text x="64" y="250" fill="#202923" font-family="Georgia" font-size="22">${escapeHtml(title).slice(0, 20)}</text></svg>`)}`;

const bookCard = (book) => {
  const image = escapeHtml(book.coverUrl || placeholder(book.title));
  const authors = escapeHtml(book.authors.length ? book.authors.join(', ') : 'Autor no indicado');
  const genre = escapeHtml(book.genres.length ? book.genres.join(' · ') : book.category);
  const stockClass = book.stock > 0 ? '' : ' out-of-stock';
  return `<article class="book-card"><div class="cover-wrap"><img src="${image}" alt="Portada de ${escapeHtml(book.title)}" loading="lazy" onerror="this.src='${placeholder(book.title)}'"><span class="genre-tag">${genre}</span></div><div class="card-body"><h3>${escapeHtml(book.title)}</h3><p class="authors">${authors}</p><dl><div><dt>ISBN</dt><dd>${escapeHtml(book.isbn || 'No indicado')}</dd></div><div><dt>Año</dt><dd>${escapeHtml(book.publicationYear)}</dd></div><div><dt>Stock</dt><dd class="stock${stockClass}">${book.stock > 0 ? `${book.stock} disponibles` : 'Agotado'}</dd></div></dl><div class="card-footer"><strong>${book.price ? `$${book.price.toFixed(2)}` : 'Precio no indicado'}</strong><span class="arrow">↗</span></div></div></article>`;
};

export const renderBooks = (element, books) => {
  element.innerHTML = books.length ? books.map(bookCard).join('') : '<div class="empty-state">No se encontraron libros en esta página.</div>';
};

export const renderPagination = (element, page, total, pageSize, onPageChange) => {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  if (pageCount <= 1) {
    element.innerHTML = '';
    return;
  }
  element.innerHTML = `<button ${page === 1 ? 'disabled' : ''} data-page="${page - 1}" aria-label="Página anterior">←</button>${Array.from({ length: pageCount }, (_, index) => index + 1).map((number) => `<button class="${number === page ? 'active' : ''}" data-page="${number}">${String(number).padStart(2, '0')}</button>`).join('')}<button ${page === pageCount ? 'disabled' : ''} data-page="${page + 1}" aria-label="Página siguiente">→</button>`;
  element.querySelectorAll('[data-page]').forEach((button) => button.addEventListener('click', () => onPageChange(Number(button.dataset.page))));
};

export const showFeedback = (element, message) => {
  element.textContent = message;
  element.hidden = !message;
};

export const setConnection = (statusElement, dotElement, connected) => {
  statusElement.textContent = connected ? 'Conectado al catálogo XML' : 'Sin conexión';
  dotElement.classList.toggle('connected', connected);
};
