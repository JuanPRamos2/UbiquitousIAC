(function () {
  var root = document.body.getAttribute("data-root") || ".";

  var exercises = [
    {
      id: "01",
      title: "Ejercicio guiado 1",
      summary: "Clasificador de modelos Cloud (IaaS, PaaS, SaaS, FaaS). Explicación del ejercicio y clasificador en el navegador.",
      status: "disponible",
      href: root + "/ejercicios/eg01.html",
      simHref: root + "/simulador.html"
    },
    {
      id: "02",
      title: "Ejercicio guiado 2",
      summary: "Se publicará en las siguientes sesiones del curso.",
      status: "proximamente",
      href: root + "/ejercicios/eg02.html"
    },
    {
      id: "03",
      title: "Ejercicio guiado 3",
      summary: "Espacio reservado para el siguiente ejercicio guiado.",
      status: "proximamente",
      href: root + "/ejercicios/eg03.html"
    },
    {
      id: "04",
      title: "Ejercicios siguientes",
      summary: "Aquí se irán agregando los ejercicios guiados del resto del semestre.",
      status: "proximamente",
      href: root + "/ejercicios/siguientes.html"
    }
  ];

  function el(tag, attrs, html) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (key) {
      node.setAttribute(key, attrs[key]);
    });
    if (html) {
      node.innerHTML = html;
    }
    return node;
  }

  function renderHeader() {
    var host = document.getElementById("site-header");
    if (!host) {
      return;
    }
    var page = document.body.getAttribute("data-page") || "";
    var site = document.body.getAttribute("data-site-root") || "../../";
    host.innerHTML =
      '<div class="topbar">' +
        '<div class="topbar-inner">' +
          '<a class="brand" href="' + site + 'index.html">' +
            '<span class="brand-mark">JR</span>' +
            '<span>UDEM<small>Integración de Aplicaciones</small></span>' +
          "</a>" +
          '<button class="menu-btn" type="button" id="menu-btn">Menú</button>' +
          "<nav id=\"main-nav\">" +
            "<ul>" +
              '<li><a href="' + site + 'index.html" data-nav="inicio">Inicio</a></li>' +
              '<li><a href="' + site + 'ejercicios/index.html" data-nav="ejercicios">Ejercicios guiados</a></li>' +
              '<li><a href="' + site + 'tareas/index.html">Tareas</a></li>' +
              '<li><a href="' + site + 'proyecto_final/index.html">Proyecto final</a></li>' +
            "</ul>" +
          "</nav>" +
        "</div>" +
      "</div>";

    var active = host.querySelector('[data-nav="' + page + '"]');
    if (active) {
      active.classList.add("active");
    }

    var button = document.getElementById("menu-btn");
    var nav = document.getElementById("main-nav");
    if (button && nav) {
      button.addEventListener("click", function () {
        nav.classList.toggle("open");
      });
    }
  }

  function renderFooter() {
    var host = document.getElementById("site-footer");
    if (!host) {
      return;
    }
    host.innerHTML =
      "Juan Pablo Ramos Salazar · Matrícula 610248 · Universidad de Monterrey · " +
      "<strong>Integración de Aplicaciones Computacionales</strong> · " +
      new Date().getFullYear();
  }

  function renderExerciseList() {
    var host = document.getElementById("exercise-list");
    if (!host) {
      return;
    }
    host.innerHTML = "";
    exercises.forEach(function (item) {
      var ready = item.status === "disponible";
      var card = el("article", { class: "card exercise-card" });
      card.innerHTML =
        '<span class="status ' + (ready ? "ready" : "soon") + '">' +
          (ready ? "Disponible" : "Próximamente") +
        "</span>" +
        "<h2>" + item.title + "</h2>" +
        "<p>" + item.summary + "</p>" +
        '<a class="btn' + (ready ? "" : " ghost") + '" href="' + item.href + '">' +
          (ready ? "Ver ejercicio" : "Ver espacio reservado") +
        "</a>" +
        (item.simHref ? '<a class="btn ghost" href="' + item.simHref + '">Probar clasificador</a>' : "");
      host.appendChild(card);
    });
  }

  function setupPhotoFallback() {
    var photo = document.getElementById("foto-alumno");
    if (!photo) {
      return;
    }
    photo.addEventListener("error", function () {
      photo.src = root + "/img/foto.svg";
    });
  }

  renderHeader();
  renderFooter();
  renderExerciseList();
  setupPhotoFallback();
})();
