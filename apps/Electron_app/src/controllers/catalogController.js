import { fetchBooks } from '../models/bookRepository.js';
import { loadConfiguration, saveConfiguration } from '../models/configuration.js';
import { renderBooks, renderPagination, setConnection, showFeedback } from '../views/catalogView.js';

const grid = document.querySelector('#book-grid');
const pagination = document.querySelector('#pagination');
const feedback = document.querySelector('#feedback');
const count = document.querySelector('#book-count');
const sourceUrl = document.querySelector('#source-url');
const status = document.querySelector('#connection-status');
const statusDot = document.querySelector('#status-dot');
const dialog = document.querySelector('#settings-dialog');
const form = document.querySelector('#settings-form');
const settingsButton = document.querySelector('#settings-button');
let configuration = loadConfiguration();
let currentPage = 1;

const updateForm = () => {
  form.baseUrl.value = configuration.baseUrl;
  form.endpoint.value = configuration.endpoint;
  form.pageSize.value = configuration.pageSize;
};

const loadPage = async (page = 1) => {
  currentPage = page;
  grid.classList.add('loading');
  showFeedback(feedback, 'Consultando el XML…');
  try {
    const result = await fetchBooks(configuration, page, configuration.pageSize);
    renderBooks(grid, result.books);
    renderPagination(pagination, page, result.total, configuration.pageSize, loadPage);
    count.textContent = `${result.total} ${result.total === 1 ? 'título' : 'títulos'}`;
    sourceUrl.textContent = result.requestedUrl;
    setConnection(status, statusDot, true);
    showFeedback(feedback, '');
  } catch (error) {
    setConnection(status, statusDot, false);
    showFeedback(feedback, `${error.message}. Revisa la URL y el endpoint en Configuración.`);
    grid.innerHTML = '';
    pagination.innerHTML = '';
    count.textContent = 'Sin resultados';
  } finally {
    grid.classList.remove('loading');
  }
};

settingsButton.addEventListener('click', () => {
  updateForm();
  dialog.showModal();
});

form.addEventListener('submit', (event) => {
  event.preventDefault();
  configuration = saveConfiguration({
    baseUrl: form.baseUrl.value,
    endpoint: form.endpoint.value,
    pageSize: form.pageSize.value,
  });
  dialog.close();
  loadPage(1);
});

dialog.addEventListener('click', (event) => {
  if (event.target === dialog) dialog.close();
});

loadPage();
