(function () {
  var STORE_KEY = "eg02-library-v3";
  var SESSION_KEY = "eg02-library-session";
  var FLASH_KEY = "eg02-library-flash";
  var CATALOGS = [
    { slug: "formats", title: "Formatos", blurb: "Tapa blanda, digital, audiolibro y demás presentaciones.", field: "name", extra: null, key: "formats" },
    { slug: "categories", title: "Categorías", blurb: "Temas generales para ordenar el acervo.", field: "name", extra: "description", key: "categories" },
    { slug: "authors", title: "Autores", blurb: "Quienes escribieron o compilaron los libros.", field: "full_name", extra: "biography", key: "authors" },
    { slug: "genres", title: "Géneros", blurb: "Novela, ensayo, programación y otros géneros.", field: "name", extra: "description", key: "genres" },
    { slug: "concepts", title: "Conceptos", blurb: "Términos que luego se definen dentro de cada libro.", field: "name", extra: "description", key: "concepts" }
  ];

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function loadStore() {
    try {
      var raw = localStorage.getItem(STORE_KEY);
      if (raw) return JSON.parse(raw);
    } catch (err) {}
    var seed = clone(window.LIBRARY_SEED);
    saveStore(seed);
    return seed;
  }

  function saveStore(store) {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(store));
    } catch (err) {
      throw new Error("No se pudo guardar la portada. Usa un JPG o PNG pequeño (el navegador se llena con fotos grandes).");
    }
  }

  function flash(type, text) {
    if (text) sessionStorage.setItem(FLASH_KEY, JSON.stringify({ type: type, text: text }));
    else {
      var raw = sessionStorage.getItem(FLASH_KEY);
      sessionStorage.removeItem(FLASH_KEY);
      return raw ? JSON.parse(raw) : null;
    }
  }

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function parseRoute() {
    var raw = (location.hash || "#/").replace(/^#/, "");
    if (!raw || raw === "") raw = "/";
    var parts = raw.split("?");
    var path = parts[0];
    if (path.charAt(0) !== "/") path = "/" + path;
    var query = {};
    if (parts[1]) {
      parts[1].split("&").forEach(function (pair) {
        var kv = pair.split("=");
        query[decodeURIComponent(kv[0] || "")] = decodeURIComponent((kv[1] || "").replace(/\+/g, " "));
      });
    }
    return { path: path.replace(/\/$/, "") || "/", query: query, segs: (path.replace(/\/$/, "") || "/").split("/").filter(Boolean) };
  }

  function go(path) {
    if (path.charAt(0) !== "#") path = "#" + (path.charAt(0) === "/" ? path : "/" + path);
    location.hash = path;
  }

  function currentUser(store) {
    var id = Number(sessionStorage.getItem(SESSION_KEY) || 0);
    return store.users.find(function (u) { return u.id === id; }) || null;
  }

  function find(list, id) {
    return list.find(function (item) { return Number(item.id) === Number(id); }) || null;
  }

  function nameOf(list, id, field) {
    var item = find(list, id);
    return item ? item[field || "name"] : "";
  }

  function hydrate(store, book) {
    if (!book) return null;
    return {
      id: book.id,
      isbn: book.isbn,
      title: book.title,
      publication_year: book.publication_year,
      price: Number(book.price),
      stock: Number(book.stock),
      format_id: book.format_id,
      category_id: book.category_id,
      description: book.description || "",
      format_name: nameOf(store.formats, book.format_id),
      category_name: nameOf(store.categories, book.category_id),
      author_ids: book.author_ids || [],
      genre_ids: book.genre_ids || [],
      authors: (book.author_ids || []).map(function (id) { return find(store.authors, id); }).filter(Boolean),
      genres: (book.genre_ids || []).map(function (id) { return find(store.genres, id); }).filter(Boolean),
      concepts: (book.concepts || []).map(function (row) {
        var concept = find(store.concepts, row.concept_id);
        return {
          concept_id: row.concept_id,
          concept_name: concept ? concept.name : "",
          definition: row.definition,
          chapter: row.chapter,
          page_number: row.page_number
        };
      }),
      images: book.images || []
    };
  }

  function searchBooks(store, isbn, title) {
    var isbnQ = (isbn || "").trim().toLowerCase();
    var titleQ = (title || "").trim().toLowerCase();
    return store.books.filter(function (book) {
      var okIsbn = !isbnQ || String(book.isbn).toLowerCase().indexOf(isbnQ) !== -1;
      var okTitle = !titleQ || String(book.title).toLowerCase().indexOf(titleQ) !== -1;
      return okIsbn && okTitle;
    }).map(function (book) { return hydrate(store, book); });
  }

  function validatePassword(password) {
    if (!password || password.length < 8) return "La contraseña debe tener al menos 8 caracteres.";
    if (!/[A-Za-z]/.test(password) || !/[0-9]/.test(password)) return "La contraseña debe incluir letras y números.";
    return null;
  }

  function validateIsbn(isbn) {
    var value = (isbn || "").trim();
    if (!/^[0-9][0-9-]{8,16}[0-9Xx]$/.test(value) && !/^[0-9]{10,13}$/.test(value)) {
      return "El ISBN no tiene un formato válido.";
    }
    return null;
  }

  function validateBook(data) {
    var errors = [];
    var isbnError = validateIsbn(data.isbn);
    if (isbnError) errors.push(isbnError);
    if (!(data.title || "").trim()) errors.push("El título es obligatorio.");
    var year = Number.parseInt(data.publication_year, 10);
    if (!Number.isInteger(year) || year < 1450 || year > 2100) errors.push("El año de publicación no es válido.");
    var price = Number(data.price);
    if (!Number.isFinite(price) || price < 0) errors.push("El precio debe ser un número mayor o igual a 0.");
    var stock = Number.parseInt(data.stock, 10);
    if (!Number.isInteger(stock) || stock < 0) errors.push("El stock debe ser un entero mayor o igual a 0.");
    if (!Number(data.format_id)) errors.push("Debe seleccionar un formato.");
    if (!Number(data.category_id)) errors.push("Debe seleccionar una categoría.");
    return errors;
  }

  function selectedValues(select) {
    return Array.prototype.slice.call(select.selectedOptions || []).map(function (opt) { return Number(opt.value); }).filter(Boolean);
  }

  function realImages(book) {
    return (book.images || []).filter(function (item) { return item && item.src; });
  }

  function coverHtml(book, tall) {
    var img = realImages(book).find(function (item) { return item.is_cover; }) || realImages(book)[0];
    if (img && img.src) {
      return '<img class="' + (tall ? "show-cover" : "") + '" src="' + esc(img.src) + '" alt="' + esc(img.alt_text || book.title) + '">';
    }
    var hue = String(book.isbn || book.id).split("").reduce(function (sum, ch) { return sum + ch.charCodeAt(0); }, 0) % 50 + 90;
    return '<div class="cover-fallback' + (tall ? " show-cover" : "") + '" style="background:hsl(' + hue + ',22%,32%)" role="img" aria-label="' + esc(book.title) + '"><span>' + esc(book.title) + "</span></div>";
  }

  function money(value) {
    return Number(value).toFixed(2);
  }

  function shell(user, inner, active) {
    var links = "";
    if (user) {
      links += '<a class="' + (active === "home" ? "is-active" : "") + '" href="#/">Inicio</a>';
      links += '<a class="' + (active === "books" ? "is-active" : "") + '" href="#/books">Catálogo</a>';
      if (user.role === "admin") {
        links += '<a class="' + (active === "new" ? "is-active" : "") + '" href="#/books/new">Nuevo libro</a>';
        links += '<a class="' + (active === "catalogs" ? "is-active" : "") + '" href="#/catalogs">Catálogos</a>';
        links += '<a class="' + (active === "users" ? "is-active" : "") + '" href="#/admin/users">Usuarios</a>';
      }
      links += '<a class="' + (active === "profile" ? "is-active" : "") + '" href="#/profile">Perfil</a>';
      links += '<button type="button" data-action="logout">Cerrar sesión</button>';
    } else {
      links += '<a class="' + (active === "login" ? "is-active" : "") + '" href="#/login">Iniciar sesión</a>';
      links += '<a class="' + (active === "register" ? "is-active" : "") + '" href="#/register">Registro</a>';
    }
    var banner = flash();
    var msg = banner ? '<div class="' + (banner.type === "error" ? "error-box" : "notice") + '">' + esc(banner.text) + "</div>" : "";
    return '<nav class="library-nav" aria-label="Librería"><strong>Librería Online</strong><div class="links">' + links + "</div></nav><div class=\"library-body\">" + msg + inner + "</div>";
  }

  function viewLogin() {
    return '<section class="library-card"><h1>Iniciar sesión</h1>' +
      '<div class="demo-accounts"><strong>Cuentas de demostración</strong><br>' +
      'Admin: <code>mariana.solis@libreriaonline.mx</code> / <code>LibreriaAdmin26</code><br>' +
      'Lector: <code>carlos.hernandez@gmail.com</code> / <code>Libreria2026</code></div>' +
      '<form data-action="login">' +
      '<label for="email">Correo</label><input id="email" name="email" type="email" required>' +
      '<label for="password">Contraseña</label><input id="password" name="password" type="password" required>' +
      '<button class="btn" type="submit">Entrar</button></form>' +
      '<p>¿No tienes cuenta? <a href="#/register">Regístrate aquí</a>.</p></section>';
  }

  function viewRegister() {
    return '<section class="library-card"><h1>Registro</h1>' +
      '<form data-action="register">' +
      '<label for="full_name">Nombre completo</label><input id="full_name" name="full_name" required>' +
      '<label for="email">Correo</label><input id="email" name="email" type="email" required>' +
      '<label for="password">Contraseña</label><input id="password" name="password" type="password" minlength="8" required>' +
      '<p class="hint">Mínimo 8 caracteres, con letras y números. La cuenta se crea como lector.</p>' +
      '<button class="btn" type="submit">Crear cuenta</button></form>' +
      '<p>¿Ya tienes cuenta? <a href="#/login">Inicia sesión</a>.</p></section>';
  }

  function view403() {
    return '<section><h1>403 — Acceso denegado</h1><p>Su cuenta no tiene permiso para esta operación administrativa.</p><p><a class="btn" href="#/">Volver al inicio</a></p></section>';
  }

  function viewDashboard(store, user) {
    return "<section><h1>Hola, " + esc(user.full_name.split(" ")[0]) + "</h1>" +
      '<p class="lede">' + (user.role === "admin"
        ? "Puedes administrar libros, catálogos y cuentas."
        : "Puedes consultar el catálogo, buscar por ISBN o título y ver el detalle de cada libro.") + "</p>" +
      '<div class="library-stats">' +
      '<div class="library-stat"><span>Libros</span><strong>' + store.books.length + "</strong></div>" +
      '<div class="library-stat"><span>Categorías</span><strong>' + store.categories.length + "</strong></div>" +
      '<div class="library-stat"><span>Autores</span><strong>' + store.authors.length + "</strong></div>" +
      '<div class="library-stat"><span>Usuarios</span><strong>' + store.users.length + "</strong></div></div>" +
      '<p><a class="btn" href="#/books">Ver libros</a></p></section>';
  }

  function viewBooks(store, user, query) {
    var books = searchBooks(store, query.isbn, query.title);
    var cards = books.length ? books.map(function (book) {
      return '<article class="book-item">' + coverHtml(book) +
        "<h3>" + esc(book.title) + "</h3>" +
        "<p><strong>ISBN:</strong> " + esc(book.isbn) + "</p>" +
        "<p><strong>Precio:</strong> $" + money(book.price) + " · <strong>Stock:</strong> " + esc(book.stock) + "</p>" +
        "<p>" + esc(book.authors.map(function (a) { return a.full_name; }).join(", ") || "Sin autores") + "</p>" +
        '<div class="inline-actions"><a class="btn" href="#/books/' + book.id + '">Ver</a>' +
        (user.role === "admin" ? '<a class="btn" href="#/books/' + book.id + '/edit">Editar</a>' : "") +
        "</div></article>";
    }).join("") : "<p>No hay libros que coincidan con la búsqueda.</p>";
    return '<section><div class="toolbar"><h1>Catálogo de libros</h1>' +
      (user.role === "admin" ? '<a class="btn" href="#/books/new">Nuevo libro</a>' : "") + "</div>" +
      '<form class="search-form" data-action="search">' +
      '<div><label for="isbn">ISBN</label><input id="isbn" name="isbn" value="' + esc(query.isbn || "") + '" placeholder="Buscar por ISBN"></div>' +
      '<div><label for="title">Título</label><input id="title" name="title" value="' + esc(query.title || "") + '" placeholder="Buscar por título"></div>' +
      '<button class="btn" type="submit">Buscar</button>' +
      '<a class="btn-ghost" href="#/books">Limpiar</a></form>' +
      '<div class="book-list">' + cards + "</div></section>";
  }

  function options(list, field, selected) {
    var selectedIds = (selected || []).map(Number);
    return list.map(function (item) {
      var isOn = selectedIds.indexOf(Number(item.id)) !== -1;
      return '<option value="' + item.id + '"' + (isOn ? " selected" : "") + ">" + esc(item[field]) + "</option>";
    }).join("");
  }

  function bookForm(store, book, action, submitLabel) {
    book = book || { author_ids: [], genre_ids: [] };
    return '<form data-action="' + action + '" data-id="' + esc(book.id || "") + '">' +
      '<div class="form-row"><div><label for="isbn">ISBN</label><input id="isbn" name="isbn" value="' + esc(book.isbn || "") + '" required></div>' +
      '<div><label for="title">Título</label><input id="title" name="title" value="' + esc(book.title || "") + '" required></div></div>' +
      '<div class="form-row"><div><label for="publication_year">Año</label><input type="number" id="publication_year" name="publication_year" min="1450" max="2100" value="' + esc(book.publication_year || "") + '" required></div>' +
      '<div><label for="price">Precio</label><input type="number" step="0.01" min="0" id="price" name="price" value="' + esc(book.price || "") + '" required></div></div>' +
      '<div class="form-row"><div><label for="stock">Stock</label><input type="number" min="0" id="stock" name="stock" value="' + esc(book.stock || 0) + '" required></div>' +
      '<div><label for="format_id">Formato</label><select id="format_id" name="format_id" required>' + options(store.formats, "name", [book.format_id]) + "</select></div></div>" +
      '<div class="form-row"><div><label for="category_id">Categoría</label><select id="category_id" name="category_id" required>' + options(store.categories, "name", [book.category_id]) + "</select></div>" +
      '<div><label for="images">Imágenes (JPG o PNG · máx. 5 MB)</label><input type="file" id="images" name="images" accept="image/png,image/jpeg,image/webp,.jpg,.jpeg,.png,.webp,.php">' +
      '<p class="hint">Los recuadros de color son un respaldo. Al guardar un JPG o PNG, esa foto pasa a ser la portada.</p>' +
      '<label for="image_alt">Texto alternativo de las nuevas imágenes</label><input id="image_alt" name="image_alt" placeholder="Portada de este libro">' +
      '<label class="inline-check"><input type="checkbox" name="cover_index" value="0" checked> Usar esta imagen como portada</label></div></div>' +
      '<div class="form-row"><div><label>Autores (varios)</label><select name="author_ids" multiple size="8">' + options(store.authors, "full_name", book.author_ids) + "</select></div>" +
      '<div><label>Géneros (varios)</label><select name="genre_ids" multiple size="8">' + options(store.genres, "name", book.genre_ids) + "</select></div></div>" +
      '<label for="description">Descripción</label><textarea id="description" name="description">' + esc(book.description || "") + "</textarea>" +
      '<div class="inline-actions"><button class="btn" type="submit">' + esc(submitLabel) + '</button><a class="btn-ghost" href="#/books">Cancelar</a></div></form>';
  }

  function viewShow(book, user) {
    var concepts = book.concepts.length
      ? '<table class="library-table"><thead><tr><th>Concepto</th><th>Definición</th><th>Capítulo</th><th>Página</th></tr></thead><tbody>' +
        book.concepts.map(function (c) {
          return "<tr><td>" + esc(c.concept_name) + "</td><td>" + esc(c.definition) + "</td><td>" + esc(c.chapter || "—") + "</td><td>" + esc(c.page_number || "—") + "</td></tr>";
        }).join("") + "</tbody></table>"
      : "<p>No hay conceptos definidos para este libro.</p>";
    var admin = user.role === "admin"
      ? '<div class="inline-actions"><a class="btn" href="#/books/' + book.id + '/edit">Editar</a><a class="btn" href="#/books/' + book.id + '/concepts">Conceptos</a><button class="btn-danger" type="button" data-action="delete-book" data-id="' + book.id + '">Eliminar</button></div>'
      : "";
    return '<section><div class="form-row"><div>' + coverHtml(book, true) + "</div><div>" +
      "<h1>" + esc(book.title) + "</h1>" +
      "<p><strong>ISBN:</strong> " + esc(book.isbn) + "</p>" +
      "<p><strong>Autor(es):</strong> " + esc(book.authors.map(function (a) { return a.full_name; }).join(", ") || "Sin autores") + "</p>" +
      "<p><strong>Géneros:</strong> " + esc(book.genres.map(function (g) { return g.name; }).join(", ") || "Sin géneros") + "</p>" +
      "<p><strong>Formato:</strong> " + esc(book.format_name) + " · <strong>Categoría:</strong> " + esc(book.category_name) + "</p>" +
      "<p><strong>Precio:</strong> $" + money(book.price) + " · <strong>Stock:</strong> " + esc(book.stock) + " · <strong>Año:</strong> " + esc(book.publication_year) + "</p>" +
      admin + "</div></div><h3>Descripción</h3><p>" + esc(book.description || "Sin descripción disponible.") + "</p>" +
      "<h3>Imágenes</h3>" + (realImages(book).length
        ? '<div class="book-list">' + realImages(book).map(function (image) {
          return '<article class="book-item"><img src="' + esc(image.src) + '" alt="' + esc(image.alt_text || book.title) + '">' +
            "<p>" + (image.is_cover ? "Portada" : "Imagen adicional") + "</p>" +
            '<p class="hint">' + esc(image.alt_text || "Sin texto alternativo") + "</p></article>";
        }).join("") + "</div>"
        : "<p>Aún no hay una fotografía de portada. El recuadro de color es solo un respaldo.</p>") +
      "<h3>Conceptos y definiciones de este libro</h3>" + concepts + "</section>";
  }

  function viewConcepts(store, book) {
    var rows = (book.concepts || []).map(function (item) {
      return "<tr><td>" + esc(item.concept_name) + "</td><td>" + esc(item.definition) + "</td><td>" + esc(item.chapter || "—") + "</td><td>" + esc(item.page_number || "—") + "</td>" +
        '<td><button class="btn-danger" type="button" data-action="delete-concept" data-book="' + book.id + '" data-concept="' + item.concept_id + '">Quitar</button></td></tr>';
    }).join("");
    return "<section><h1>Conceptos de " + esc(book.title) + "</h1>" +
      '<p class="lede">Anota cómo se explica cada término en este libro. El mismo término puede tener otra explicación en un título distinto.</p>' +
      '<form data-action="save-concept" data-id="' + book.id + '">' +
      '<div class="form-row"><div><label for="concept_id">Concepto</label><select id="concept_id" name="concept_id" required>' + options(store.concepts, "name") + "</select></div>" +
      '<div><label for="chapter">Capítulo</label><input id="chapter" name="chapter"></div></div>' +
      '<div class="form-row"><div><label for="page_number">Página</label><input type="number" min="1" id="page_number" name="page_number"></div>' +
      '<div><label for="definition">Definición en este libro</label><textarea id="definition" name="definition" required></textarea></div></div>' +
      '<button class="btn" type="submit">Guardar definición</button></form>' +
      '<table class="library-table"><thead><tr><th>Concepto</th><th>Definición</th><th>Capítulo</th><th>Página</th><th></th></tr></thead><tbody>' + rows + "</tbody></table>" +
      '<p><a class="btn-ghost" href="#/books/' + book.id + '">Volver al libro</a></p></section>';
  }

  function viewCatalogIndex() {
    return "<section><h1>Catálogos</h1><p class=\"lede\">Organiza los listados que usa la librería. Los libros se relacionan con estos listados desde la ficha de cada título.</p>" +
      '<div class="catalog-grid">' + CATALOGS.map(function (catalog) {
        return '<a class="catalog-card" href="#/catalogs/' + catalog.slug + '"><h2>' + esc(catalog.title) + "</h2><p>" + esc(catalog.blurb) + '</p><span class="catalog-card-action">Abrir</span></a>';
      }).join("") + "</div></section>";
  }

  function viewCatalogList(store, catalog) {
    var items = store[catalog.key];
    var rows = items.map(function (item) {
      return "<tr><td><form class=\"inline-actions\" data-action=\"update-catalog\" data-slug=\"" + catalog.slug + "\" data-id=\"" + item.id + "\">" +
        '<input name="' + catalog.field + '" value="' + esc(item[catalog.field]) + '" required>' +
        (catalog.extra ? '<input name="' + catalog.extra + '" value="' + esc(item[catalog.extra] || "") + '">' : "") +
        '<button class="btn" type="submit">Guardar cambios</button></form></td>' +
        '<td><button class="btn-danger" type="button" data-action="delete-catalog" data-slug="' + catalog.slug + '" data-id="' + item.id + '">Eliminar</button></td></tr>';
    }).join("");
    return '<section><p class="breadcrumb"><a href="#/catalogs">Catálogos</a> · ' + esc(catalog.title) + "</p><h1>" + esc(catalog.title) + "</h1>" +
      '<form class="add-form" data-action="create-catalog" data-slug="' + catalog.slug + '"><h2>Agregar</h2>' +
      "<label>" + (catalog.field === "full_name" ? "Nombre completo" : "Nombre") + "</label>" +
      '<input name="' + catalog.field + '" required>' +
      (catalog.extra ? "<label>" + (catalog.extra === "biography" ? "Biografía" : "Descripción") + '</label><textarea name="' + catalog.extra + '"></textarea>' : "") +
      '<button class="btn" type="submit">Guardar</button></form>' +
      '<table class="library-table"><thead><tr><th>Nombre</th><th></th></tr></thead><tbody>' + rows + "</tbody></table></section>";
  }

  function viewProfile(user) {
    return '<section class="library-card"><h1>Mi perfil</h1>' +
      "<p><strong>Nombre:</strong> " + esc(user.full_name) + "</p>" +
      "<p><strong>Correo:</strong> " + esc(user.email) + "</p>" +
      "<p><strong>Rol:</strong> " + (user.role === "admin" ? "Administrador" : "Usuario registrado") + "</p>" +
      '<p><a class="btn" href="#/">Volver al inicio</a></p></section>';
  }

  function viewUsers(store) {
    var rows = store.users.map(function (user) {
      return "<tr><td>" + esc(user.full_name) + "</td><td>" + esc(user.email) + "</td><td>" + (user.role === "admin" ? "Administrador" : "Lector") + "</td><td>" +
        '<form class="inline-actions" data-action="set-role" data-id="' + user.id + '">' +
        '<select name="role"><option value="client"' + (user.role === "client" ? " selected" : "") + '>Lector</option><option value="admin"' + (user.role === "admin" ? " selected" : "") + ">Administrador</option></select>" +
        '<button class="btn" type="submit">Guardar</button></form>' +
        '<button class="btn-danger" type="button" data-action="delete-user" data-id="' + user.id + '">Eliminar</button></td></tr>';
    }).join("");
    return "<section><h1>Usuarios</h1><p class=\"lede\">Cuentas de la librería. Solo una persona puede ser administradora.</p>" +
      '<table class="library-table"><thead><tr><th>Nombre</th><th>Correo</th><th>Rol</th><th>Acciones</th></tr></thead><tbody>' + rows + "</tbody></table></section>";
  }

  function catalogBySlug(slug) {
    return CATALOGS.find(function (item) { return item.slug === slug; }) || null;
  }

  function usedCatalog(store, catalog, id) {
    if (catalog.key === "formats") return store.books.some(function (b) { return Number(b.format_id) === Number(id); });
    if (catalog.key === "categories") return store.books.some(function (b) { return Number(b.category_id) === Number(id); });
    if (catalog.key === "authors") return store.books.some(function (b) { return (b.author_ids || []).map(Number).indexOf(Number(id)) !== -1; });
    if (catalog.key === "genres") return store.books.some(function (b) { return (b.genre_ids || []).map(Number).indexOf(Number(id)) !== -1; });
    if (catalog.key === "concepts") return store.books.some(function (b) { return (b.concepts || []).some(function (c) { return Number(c.concept_id) === Number(id); }); });
    return false;
  }

  function nextId(store, key) {
    var value = store.nextIds[key] || 1;
    store.nextIds[key] = value + 1;
    return value;
  }

  function fileToDataUrl(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onerror = function () { reject(new Error("No se pudo leer la imagen.")); };
      reader.onload = function () {
        var img = new Image();
        img.onload = function () {
          var max = 720;
          var width = img.width || max;
          var height = img.height || max;
          if (width > max || height > max) {
            var scale = Math.min(max / width, max / height);
            width = Math.round(width * scale);
            height = Math.round(height * scale);
          }
          var canvas = document.createElement("canvas");
          canvas.width = width;
          canvas.height = height;
          canvas.getContext("2d").drawImage(img, 0, 0, width, height);
          resolve(canvas.toDataURL("image/jpeg", 0.82));
        };
        img.onerror = function () {
          reject(new Error("Ese archivo no se pudo usar como imagen. Elige un JPG o PNG (no HEIC del iPhone)."));
        };
        img.src = reader.result;
      };
      reader.readAsDataURL(file);
    });
  }

  function readImages(form) {
    var input = form.querySelector('input[name="images"]');
    var files = input && input.files ? Array.prototype.slice.call(input.files) : [];
    if (!files.length) return Promise.resolve([]);
    var alt = ((form.image_alt && form.image_alt.value) || "").trim();
    var asCover = !form.cover_index || form.cover_index.checked;
    return files.reduce(function (chain, file, index) {
      return chain.then(function (loaded) {
        var name = (file.name || "").toLowerCase();
        if (name.slice(-4) === ".php" || file.type === "application/x-php" || file.type === "text/x-php") {
          throw new Error("No se permiten archivos .php.");
        }
        var okType = file.type === "image/jpeg" || file.type === "image/png" || file.type === "image/webp" || /\.(jpe?g|png|webp)$/.test(name);
        if (!okType) throw new Error("Solo se aceptan JPG, PNG o WebP. Si la foto es del iPhone, expórtala a JPG.");
        if (file.size > 5 * 1024 * 1024) throw new Error("Cada imagen debe pesar 5 MB o menos.");
        return fileToDataUrl(file).then(function (src) {
          loaded.push({ src: src, alt_text: alt || file.name, is_cover: asCover && index === 0 });
          return loaded;
        });
      });
    }, Promise.resolve([]));
  }

  function payloadFromForm(form) {
    return {
      isbn: form.isbn.value.trim(),
      title: form.title.value.trim(),
      publication_year: form.publication_year.value,
      price: form.price.value,
      stock: form.stock.value,
      format_id: Number(form.format_id.value),
      category_id: Number(form.category_id.value),
      description: form.description.value,
      author_ids: selectedValues(form.author_ids),
      genre_ids: selectedValues(form.genre_ids)
    };
  }

  function render() {
    var app = document.getElementById("app");
    if (!app || !window.LIBRARY_SEED) return;
    var store = loadStore();
    var user = currentUser(store);
    var route = parseRoute();
    var segs = route.segs;
    var html;
    var active = "home";

    if (!user && segs[0] !== "login" && segs[0] !== "register") {
      if (segs[0] === "books" || segs[0] === "catalogs" || segs[0] === "admin" || segs[0] === "profile") {
        go("/login");
        return;
      }
    }

    if (!user && (!segs[0] || segs[0] === "")) {
      html = shell(null, viewLogin(), "login");
    } else if (segs[0] === "login") {
      if (user) { go("/"); return; }
      html = shell(null, viewLogin(), "login");
    } else if (segs[0] === "register") {
      if (user) { go("/"); return; }
      html = shell(null, viewRegister(), "register");
    } else if (segs[0] === "403") {
      html = shell(user, view403(), "home");
    } else if (!segs.length) {
      html = shell(user, viewDashboard(store, user), "home");
    } else if (segs[0] === "profile") {
      html = shell(user, viewProfile(user), "profile");
    } else if (segs[0] === "admin" && segs[1] === "users") {
      if (user.role !== "admin") { go("/403"); return; }
      html = shell(user, viewUsers(store), "users");
    } else if (segs[0] === "catalogs") {
      if (user.role !== "admin") { go("/403"); return; }
      if (!segs[1]) html = shell(user, viewCatalogIndex(), "catalogs");
      else {
        var catalog = catalogBySlug(segs[1]);
        if (!catalog) html = shell(user, "<h1>404</h1><p>Catálogo no encontrado.</p>", "catalogs");
        else html = shell(user, viewCatalogList(store, catalog), "catalogs");
      }
    } else if (segs[0] === "books") {
      if (segs[1] === "new") {
        if (user.role !== "admin") { go("/403"); return; }
        html = shell(user, "<section><h1>Registrar nuevo libro</h1>" + bookForm(store, {}, "create-book", "Guardar libro") + "</section>", "new");
        active = "new";
      } else if (segs[1] && segs[2] === "edit") {
        if (user.role !== "admin") { go("/403"); return; }
        var editBook = hydrate(store, find(store.books, segs[1]));
        if (!editBook) html = shell(user, "<h1>Libro no encontrado</h1>", "books");
        else html = shell(user, "<section><h1>Editar " + esc(editBook.title) + "</h1>" + bookForm(store, editBook, "update-book", "Guardar cambios") + "</section>", "books");
      } else if (segs[1] && segs[2] === "concepts") {
        if (user.role !== "admin") { go("/403"); return; }
        var conceptBook = hydrate(store, find(store.books, segs[1]));
        if (!conceptBook) html = shell(user, "<h1>Libro no encontrado</h1>", "books");
        else html = shell(user, viewConcepts(store, conceptBook), "books");
      } else if (segs[1]) {
        var shown = hydrate(store, find(store.books, segs[1]));
        if (!shown) html = shell(user, "<h1>Libro no encontrado</h1>", "books");
        else html = shell(user, viewShow(shown, user), "books");
      } else {
        html = shell(user, viewBooks(store, user, route.query), "books");
      }
    } else {
      html = shell(user, "<h1>404</h1><p>Página no encontrada.</p><p><a class=\"btn\" href=\"#/\">Inicio</a></p>", "home");
    }
    app.innerHTML = html;
  }

  function saveBookFromForm(form, existingId) {
    var data = payloadFromForm(form);
    var errors = validateBook(data);
    if (errors.length) {
      flash("error", errors.join(" "));
      render();
      return Promise.resolve();
    }
    var store = loadStore();
    var duplicate = store.books.find(function (book) {
      return book.isbn === data.isbn && (!existingId || Number(book.id) !== Number(existingId));
    });
    if (duplicate) {
      flash("error", "Ese ISBN ya está registrado.");
      render();
      return Promise.resolve();
    }
    return readImages(form).then(function (images) {
      if (existingId) {
        var existing = find(store.books, existingId);
        if (!existing) {
          flash("error", "Libro no encontrado.");
          render();
          return;
        }
        existing.isbn = data.isbn;
        existing.title = data.title;
        existing.publication_year = Number(data.publication_year);
        existing.price = Number(data.price);
        existing.stock = Number(data.stock);
        existing.format_id = data.format_id;
        existing.category_id = data.category_id;
        existing.description = data.description;
        existing.author_ids = data.author_ids;
        existing.genre_ids = data.genre_ids;
        existing.images = realImages(existing);
        if (images.length) {
          if (!existing.images.some(function (img) { return img.is_cover; })) {
            images[0].is_cover = true;
          }
          if (images.some(function (img) { return img.is_cover; })) {
            existing.images.forEach(function (img) { img.is_cover = false; });
          }
          images.forEach(function (img) {
            img.id = nextId(store, "images");
            existing.images.push(img);
          });
        }
        flash("ok", "Libro actualizado.");
        saveStore(store);
        go("/books/" + existing.id);
      } else {
        var created = {
          id: nextId(store, "books"),
          isbn: data.isbn,
          title: data.title,
          publication_year: Number(data.publication_year),
          price: Number(data.price),
          stock: Number(data.stock),
          format_id: data.format_id,
          category_id: data.category_id,
          description: data.description,
          author_ids: data.author_ids,
          genre_ids: data.genre_ids,
          concepts: [],
          images: images.map(function (img) {
            img.id = nextId(store, "images");
            return img;
          })
        };
        store.books.push(created);
        flash("ok", "Libro creado.");
        saveStore(store);
        go("/books/" + created.id);
      }
    }).catch(function (err) {
      flash("error", err.message);
      render();
    });
  }

  document.addEventListener("submit", function (event) {
    var form = event.target;
    var action = form.getAttribute("data-action");
    if (!action) return;
    event.preventDefault();
    var store = loadStore();
    var user = currentUser(store);

    if (action === "login") {
      var email = form.email.value.trim().toLowerCase();
      var found = store.users.find(function (item) { return item.email === email && item.password === form.password.value; });
      if (!found) {
        flash("error", "Credenciales incorrectas.");
        render();
        return;
      }
      sessionStorage.setItem(SESSION_KEY, String(found.id));
      go("/");
      return;
    }

    if (action === "register") {
      var pwdError = validatePassword(form.password.value);
      if (!form.full_name.value.trim() || !form.email.value.trim() || !form.password.value) {
        flash("error", "Todos los campos son obligatorios.");
        render();
        return;
      }
      if (pwdError) {
        flash("error", pwdError);
        render();
        return;
      }
      var newEmail = form.email.value.trim().toLowerCase();
      if (store.users.some(function (item) { return item.email === newEmail; })) {
        flash("error", "Ese correo ya está registrado.");
        render();
        return;
      }
      var createdUser = {
        id: nextId(store, "users"),
        full_name: form.full_name.value.trim(),
        email: newEmail,
        password: form.password.value,
        role: "client",
        created_at: new Date().toISOString()
      };
      store.users.push(createdUser);
      saveStore(store);
      sessionStorage.setItem(SESSION_KEY, String(createdUser.id));
      flash("ok", "Cuenta creada. Bienvenido a la librería.");
      go("/");
      return;
    }

    if (action === "search") {
      var isbn = encodeURIComponent(form.isbn.value.trim());
      var title = encodeURIComponent(form.title.value.trim());
      go("/books?isbn=" + isbn + "&title=" + title);
      return;
    }

    if (action === "create-book") {
      if (!user || user.role !== "admin") { go("/403"); return; }
      saveBookFromForm(form, null);
      return;
    }

    if (action === "update-book") {
      if (!user || user.role !== "admin") { go("/403"); return; }
      saveBookFromForm(form, form.getAttribute("data-id"));
      return;
    }

    if (action === "save-concept") {
      if (!user || user.role !== "admin") { go("/403"); return; }
      var book = find(store.books, form.getAttribute("data-id"));
      var definition = form.definition.value.trim();
      var conceptId = Number(form.concept_id.value);
      if (!book || !definition || !conceptId) {
        flash("error", "Seleccione un concepto y escriba una definición.");
        render();
        return;
      }
      book.concepts = book.concepts || [];
      var existingConcept = book.concepts.find(function (row) { return Number(row.concept_id) === conceptId; });
      var row = { concept_id: conceptId, definition: definition, chapter: form.chapter.value, page_number: Number(form.page_number.value) || null };
      if (existingConcept) {
        existingConcept.definition = row.definition;
        existingConcept.chapter = row.chapter;
        existingConcept.page_number = row.page_number;
      } else book.concepts.push(row);
      saveStore(store);
      flash("ok", "Definición guardada.");
      go("/books/" + book.id + "/concepts");
      return;
    }

    if (action === "create-catalog" || action === "update-catalog") {
      if (!user || user.role !== "admin") { go("/403"); return; }
      var catalog = catalogBySlug(form.getAttribute("data-slug"));
      if (!catalog) return;
      var primary = (form[catalog.field].value || "").trim();
      if (!primary) {
        flash("error", "El nombre es obligatorio.");
        render();
        return;
      }
      if (action === "create-catalog") {
        var createdItem = { id: nextId(store, catalog.key) };
        createdItem[catalog.field] = primary;
        if (catalog.extra) createdItem[catalog.extra] = form[catalog.extra].value;
        store[catalog.key].push(createdItem);
        flash("ok", catalog.title.slice(0, -1) + " creado.");
      } else {
        var item = find(store[catalog.key], form.getAttribute("data-id"));
        if (item) {
          item[catalog.field] = primary;
          if (catalog.extra) item[catalog.extra] = form[catalog.extra].value;
          flash("ok", "Registro actualizado.");
        }
      }
      saveStore(store);
      go("/catalogs/" + catalog.slug);
      return;
    }

    if (action === "set-role") {
      if (!user || user.role !== "admin") { go("/403"); return; }
      var target = find(store.users, form.getAttribute("data-id"));
      var role = form.role.value;
      if (!target) return;
      if (role === "admin") {
        var otherAdmin = store.users.some(function (item) { return item.role === "admin" && item.id !== target.id; });
        if (otherAdmin) {
          flash("error", "Solo puede haber un administrador.");
          render();
          return;
        }
      }
      if (target.id === user.id && role !== "admin") {
        flash("error", "No puede quitarse el rol de administrador mientras está autenticado.");
        render();
        return;
      }
      target.role = role;
      saveStore(store);
      flash("ok", "Rol actualizado.");
      go("/admin/users");
    }
  });

  document.addEventListener("click", function (event) {
    var btn = event.target.closest("[data-action]");
    if (!btn || btn.tagName === "FORM") return;
    if (btn.tagName === "BUTTON" && btn.getAttribute("type") === "submit") return;
    var action = btn.getAttribute("data-action");
    if (!action) return;
    if (["logout", "delete-book", "delete-concept", "delete-catalog", "delete-user"].indexOf(action) === -1) return;
    event.preventDefault();
    var store = loadStore();
    var user = currentUser(store);

    if (action === "logout") {
      sessionStorage.removeItem(SESSION_KEY);
      go("/login");
      return;
    }
    if (!user || user.role !== "admin") { go("/403"); return; }

    if (action === "delete-book") {
      if (!confirm("¿Eliminar este libro?")) return;
      store.books = store.books.filter(function (book) { return Number(book.id) !== Number(btn.getAttribute("data-id")); });
      saveStore(store);
      flash("ok", "Libro eliminado.");
      go("/books");
      return;
    }
    if (action === "delete-concept") {
      var book = find(store.books, btn.getAttribute("data-book"));
      if (book) book.concepts = (book.concepts || []).filter(function (row) { return Number(row.concept_id) !== Number(btn.getAttribute("data-concept")); });
      saveStore(store);
      flash("ok", "Definición eliminada.");
      go("/books/" + btn.getAttribute("data-book") + "/concepts");
      return;
    }
    if (action === "delete-catalog") {
      var catalog = catalogBySlug(btn.getAttribute("data-slug"));
      var id = btn.getAttribute("data-id");
      if (!catalog) return;
      if (usedCatalog(store, catalog, id)) {
        flash("error", "No se puede eliminar: el registro está en uso (restricción RESTRICT).");
        render();
        return;
      }
      if (!confirm("¿Eliminar este registro?")) return;
      store[catalog.key] = store[catalog.key].filter(function (item) { return Number(item.id) !== Number(id); });
      saveStore(store);
      flash("ok", "Registro eliminado.");
      go("/catalogs/" + catalog.slug);
      return;
    }
    if (action === "delete-user") {
      var uid = Number(btn.getAttribute("data-id"));
      if (uid === user.id) {
        flash("error", "No puede eliminar su propia cuenta mientras está autenticado.");
        render();
        return;
      }
      if (!confirm("¿Eliminar esta cuenta?")) return;
      store.users = store.users.filter(function (item) { return item.id !== uid; });
      saveStore(store);
      flash("ok", "Usuario eliminado.");
      go("/admin/users");
    }
  });

  window.addEventListener("hashchange", render);
  if (!location.hash) location.hash = "#/login";
  render();
})();
