const STORAGE_KEY = "library.soap.endpoint";
const DEFAULT_ENDPOINT = "http://127.0.0.1:5001";

const endpointInput = document.getElementById("endpoint");
const statusEl = document.getElementById("status");
const grid = document.getElementById("grid");

function normalizeEndpoint(value) {
  const raw = (value || DEFAULT_ENDPOINT).trim();
  return raw.replace(/\/+$/, "") || DEFAULT_ENDPOINT;
}

function loadSavedEndpoint() {
  const saved = window.localStorage.getItem(STORAGE_KEY);
  endpointInput.value = saved || DEFAULT_ENDPOINT;
  return normalizeEndpoint(endpointInput.value);
}

function saveEndpoint() {
  const endpoint = normalizeEndpoint(endpointInput.value);
  endpointInput.value = endpoint;
  window.localStorage.setItem(STORAGE_KEY, endpoint);
  return endpoint;
}

function setStatus(message, kind) {
  statusEl.textContent = message;
  statusEl.className = "status" + (kind ? " " + kind : "");
}

function textOf(node, tag) {
  const child = node.getElementsByTagName(tag)[0];
  return child ? (child.textContent || "").trim() : "";
}

function authorsOf(node) {
  return Array.from(node.getElementsByTagName("author"))
    .map((el) => (el.textContent || "").trim())
    .filter(Boolean);
}

function coverOf(node) {
  const cover = textOf(node, "coverUrl");
  if (cover) return cover;
  const image = node.getElementsByTagName("image")[0];
  if (!image) return "";
  return textOf(image, "url");
}

function parseBooksXml(xmlText) {
  const doc = new DOMParser().parseFromString(xmlText, "application/xml");
  if (doc.querySelector("parsererror")) {
    throw new Error("El microservicio no devolvió XML válido.");
  }
  return Array.from(doc.getElementsByTagName("book"))
    .filter((node) => node.getElementsByTagName("isbn").length)
    .map((node) => ({
      isbn: textOf(node, "isbn"),
      title: textOf(node, "title") || "Sin título",
      authors: authorsOf(node),
      year: textOf(node, "publicationYear"),
      price: textOf(node, "price"),
      coverUrl: coverOf(node),
    }));
}

function resolveUrl(endpoint, path) {
  if (!path) return "";
  if (/^https?:\/\//i.test(path)) return path;
  return endpoint + (path.startsWith("/") ? path : "/" + path);
}

function formatPrice(value) {
  if (!value) return "Precio no informado";
  const number = Number(value);
  if (Number.isNaN(number)) return value;
  return "$" + number.toFixed(2) + " MXN";
}

function renderBooks(books, endpoint) {
  grid.innerHTML = "";
  if (!books.length) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "No hay libros en la respuesta XML.";
    grid.appendChild(empty);
    return;
  }
  const fragment = document.createDocumentFragment();
  for (const book of books) {
    const card = document.createElement("article");
    card.className = "card";
    const coverWrap = document.createElement("div");
    coverWrap.className = "cover";
    const img = document.createElement("img");
    img.alt = "Portada de " + book.title;
    img.src = resolveUrl(endpoint, book.coverUrl);
    coverWrap.appendChild(img);
    const body = document.createElement("div");
    body.className = "body";
    body.innerHTML =
      "<h2 class=\"title\"></h2>" +
      "<p class=\"meta authors\"></p>" +
      "<p class=\"meta year\"></p>" +
      "<p class=\"meta isbn\"></p>" +
      "<p class=\"price\"></p>";
    body.querySelector(".title").textContent = book.title;
    body.querySelector(".authors").textContent = book.authors.length
      ? "Autores: " + book.authors.join(", ")
      : "Autores: no informados";
    body.querySelector(".year").textContent = book.year
      ? "Año de publicación: " + book.year
      : "Año de publicación: no informado";
    body.querySelector(".isbn").textContent = "ISBN: " + (book.isbn || "—");
    body.querySelector(".price").textContent = formatPrice(book.price);
    card.appendChild(coverWrap);
    card.appendChild(body);
    fragment.appendChild(card);
  }
  grid.appendChild(fragment);
}

async function loadCatalog(path) {
  const endpoint = saveEndpoint();
  const url = endpoint + path;
  setStatus("Cargando " + url + " …");
  try {
    const response = await fetch(url, { headers: { Accept: "application/xml" } });
    if (!response.ok) {
      throw new Error("HTTP " + response.status + " al pedir " + url);
    }
    const xmlText = await response.text();
    const books = parseBooksXml(xmlText);
    renderBooks(books, endpoint);
    setStatus(books.length + " libros desde " + url, "ok");
  } catch (error) {
    grid.innerHTML = "";
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent =
      "No se pudo leer el XML. Arranca Flask con ./run-flask.sh y revisa el endpoint.";
    grid.appendChild(empty);
    setStatus(String(error.message || error), "error");
  }
}

document.getElementById("save").addEventListener("click", () => {
  const endpoint = saveEndpoint();
  setStatus("Endpoint guardado en LocalStorage: " + endpoint, "ok");
});
document.getElementById("load-books").addEventListener("click", () => loadCatalog("/books"));
document.getElementById("load-images").addEventListener("click", () => loadCatalog("/books-images"));
endpointInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") loadCatalog("/books");
});

loadSavedEndpoint();
loadCatalog("/books");
