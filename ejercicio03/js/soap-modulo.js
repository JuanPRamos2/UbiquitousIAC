(function (global) {
  "use strict";

  var TNS = "http://udem.edu.mx/iac/library-classifier";
  var SOAP = "http://schemas.xmlsoap.org/soap/envelope/";
  var WSSE = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd";
  var STORAGE_KEY = "iac-eg03-soap-demo";
  var MODELS = ["IaaS", "PaaS", "SaaS", "FaaS"];
  var STATS_USER = "soap_stats";
  var STATS_PASS = "laboratorio";

  var CATALOGO = [
    {
      concept_id: 101,
      concept_name: "Máquinas virtuales",
      definition: "Infraestructura con máquinas virtuales, almacenamiento y redes para instalar el propio sistema operativo.",
      isbn: "9780132350884",
      book_title: "Clean Code",
      category_name: "Tecnología"
    },
    {
      concept_id: 102,
      concept_name: "Plataforma de despliegue",
      definition: "Desplegar la aplicación web sin administrar directamente servidores ni sistemas operativos.",
      isbn: "9780132350884",
      book_title: "Clean Code",
      category_name: "Tecnología"
    },
    {
      concept_id: 103,
      concept_name: "Correo en el navegador",
      definition: "Los empleados utilizan una aplicación de correo electrónico desde el navegador con suscripción mensual.",
      isbn: "9780062316097",
      book_title: "Sapiens",
      category_name: "Ciencias sociales"
    },
    {
      concept_id: 104,
      concept_name: "Función serverless",
      definition: "Ejecutar una función automáticamente cada vez que un usuario suba una imagen al almacenamiento Cloud.",
      isbn: "9780307474728",
      book_title: "Cien años de soledad",
      category_name: "Literatura"
    }
  ];

  function escapeXml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&apos;");
  }

  function envelope(bodyXml, headerXml) {
    return (
      '<?xml version="1.0" encoding="UTF-8"?>\n' +
      '<soap:Envelope xmlns:soap="' + SOAP + '" xmlns:tns="' + TNS + '" xmlns:wsse="' + WSSE + '">\n' +
      "  <soap:Header>" + (headerXml || "") + "</soap:Header>\n" +
      "  <soap:Body>\n" + bodyXml + "\n  </soap:Body>\n" +
      "</soap:Envelope>"
    );
  }

  function securityHeader(user, pass) {
    return (
      '\n    <wsse:Security>\n      <wsse:UsernameToken>\n' +
      "        <wsse:Username>" + escapeXml(user) + "</wsse:Username>\n" +
      "        <wsse:Password>" + escapeXml(pass) + "</wsse:Password>\n" +
      "      </wsse:UsernameToken>\n    </wsse:Security>\n  "
    );
  }

  function faultXml(code, http, name, message) {
    return envelope(
      "    <soap:Fault>\n" +
        "      <faultcode>" + (http >= 500 ? "soap:Server" : "soap:Client") + "</faultcode>\n" +
        "      <faultstring>" + escapeXml(message) + "</faultstring>\n" +
        "      <detail>\n        <tns:" + name + ">\n" +
        "          <tns:codigo>" + http + "</tns:codigo>\n" +
        "          <tns:mensaje>" + escapeXml(message) + "</tns:mensaje>\n" +
        "        </tns:" + name + ">\n      </detail>\n" +
        "    </soap:Fault>"
    );
  }

  function loadState() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (raw) return JSON.parse(raw);
    } catch (err) {}
    return { clasificadores: {}, clasificaciones: [], clientes: {}, nextId: 1 };
  }

  function saveState(state) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }

  function localName(node) {
    if (!node || !node.tagName) return "";
    return node.tagName.split(":").pop();
  }

  function childText(parent, name) {
    if (!parent) return "";
    var kids = parent.children;
    for (var i = 0; i < kids.length; i++) {
      if (localName(kids[i]) === name) {
        return (kids[i].textContent || "").trim();
      }
    }
    return "";
  }

  function findByName(parent, name) {
    if (!parent) return null;
    var kids = parent.children;
    for (var i = 0; i < kids.length; i++) {
      if (localName(kids[i]) === name) return kids[i];
    }
    return null;
  }

  function parseEnvelope(xmlText) {
    var doc;
    try {
      doc = new DOMParser().parseFromString(xmlText, "text/xml");
    } catch (err) {
      throw { fault: true, xml: faultXml("Client", 400, "ClientFault", "El documento XML no es un Envelope SOAP válido") };
    }
    if (doc.getElementsByTagName("parsererror").length) {
      throw { fault: true, xml: faultXml("Client", 400, "ClientFault", "El documento XML no es un Envelope SOAP válido") };
    }
    var root = doc.documentElement;
    if (localName(root) !== "Envelope") {
      throw { fault: true, xml: faultXml("Client", 400, "ClientFault", "La raíz del documento debe ser soap:Envelope") };
    }
    var header = findByName(root, "Header");
    var body = findByName(root, "Body");
    if (!body) {
      throw { fault: true, xml: faultXml("Client", 400, "ClientFault", "El Envelope no contiene soap:Body") };
    }
    var payload = null;
    for (var i = 0; i < body.children.length; i++) {
      if (localName(body.children[i]) !== "Fault") {
        payload = body.children[i];
        break;
      }
    }
    return { header: header, payload: payload };
  }

  function requireField(payload, field) {
    var value = childText(payload, field);
    if (!value) {
      throw { fault: true, xml: faultXml("Client", 400, "ClientFault", "El campo " + field + " es obligatorio") };
    }
    return value;
  }

  function requireEmail(payload) {
    var correo = requireField(payload, "correo").toLowerCase();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(correo)) {
      throw { fault: true, xml: faultXml("Client", 400, "ClientFault", "El correo no tiene un formato válido") };
    }
    return correo;
  }

  function handleRequest(xmlText) {
    var parsed = parseEnvelope(xmlText);
    if (!parsed.payload) {
      throw { fault: true, xml: faultXml("Client", 400, "ClientFault", "El Body SOAP no contiene una operación") };
    }
    var op = localName(parsed.payload);
    if (op === "ObtenerEstadisticasPorModelo") {
      var security = findByName(parsed.header, "Security");
      var token = findByName(security, "UsernameToken");
      var user = childText(token, "Username");
      var pass = childText(token, "Password");
      if (user !== STATS_USER || pass !== STATS_PASS) {
        throw { fault: true, xml: faultXml("Client", 401, "SecurityFault", "Credenciales WS-Security inválidas o ausentes") };
      }
    }
    if (op === "ObtenerConceptosPendientes") return pendientes(parsed.payload);
    if (op === "RegistrarClasificacion") return registrar(parsed.payload);
    if (op === "ObtenerProgresoUsuario") return progreso(parsed.payload);
    if (op === "ObtenerEstadisticasPorModelo") return estadisticas();
    throw { fault: true, xml: faultXml("Client", 400, "ClientFault", "Operación no soportada: " + op) };
  }

  function pendientes(payload) {
    var correo = requireEmail(payload);
    var tipo = childText(payload, "tipoCliente") || "desktop-web";
    var state = loadState();
    bumpCliente(state, tipo, correo);
    saveState(state);
    var hechos = {};
    state.clasificaciones.forEach(function (row) {
      if (row.correo === correo) hechos[row.concept_id] = true;
    });
    var items = CATALOGO.filter(function (item) { return !hechos[item.concept_id]; });
    var inner = items.map(function (item) {
      return (
        "      <tns:concepto>\n" +
        "        <tns:conceptId>" + item.concept_id + "</tns:conceptId>\n" +
        "        <tns:conceptName>" + escapeXml(item.concept_name) + "</tns:conceptName>\n" +
        "        <tns:definition>" + escapeXml(item.definition) + "</tns:definition>\n" +
        "        <tns:isbn>" + escapeXml(item.isbn) + "</tns:isbn>\n" +
        "        <tns:bookTitle>" + escapeXml(item.book_title) + "</tns:bookTitle>\n" +
        "        <tns:categoryName>" + escapeXml(item.category_name) + "</tns:categoryName>\n" +
        "      </tns:concepto>"
      );
    }).join("\n");
    return envelope(
      "    <tns:ObtenerConceptosPendientesResponse>\n" +
        "      <tns:total>" + items.length + "</tns:total>\n" +
        inner +
        "\n    </tns:ObtenerConceptosPendientesResponse>"
    );
  }

  function registrar(payload) {
    var nombre = requireField(payload, "nombre");
    var apellidos = requireField(payload, "apellidos");
    var correo = requireEmail(payload);
    var conceptId = parseInt(requireField(payload, "conceptId"), 10);
    var isbn = requireField(payload, "isbn");
    var modelo = requireField(payload, "modelo");
    var tipo = requireField(payload, "tipoCliente");
    if (MODELS.indexOf(modelo) === -1) {
      throw { fault: true, xml: faultXml("Client", 400, "ValidationFault", "El modelo debe ser IaaS, PaaS, SaaS o FaaS") };
    }
    if (isNaN(conceptId)) {
      throw { fault: true, xml: faultXml("Client", 400, "ClientFault", "El campo conceptId debe ser un entero") };
    }
    var match = CATALOGO.filter(function (item) {
      return item.concept_id === conceptId && item.isbn === isbn;
    })[0];
    if (!match) {
      throw { fault: true, xml: faultXml("Client", 404, "NotFoundFault", "El concepto no existe en el catálogo de la librería") };
    }
    var state = loadState();
    var dup = state.clasificaciones.some(function (row) {
      return row.correo === correo && row.concept_id === conceptId;
    });
    if (dup) {
      throw { fault: true, xml: faultXml("Client", 409, "DuplicadoFault", "El concepto ya fue clasificado por este usuario") };
    }
    var id = state.nextId++;
    state.clasificadores[correo] = { nombre: nombre, apellidos: apellidos, correo: correo };
    state.clasificaciones.push({
      id: id,
      correo: correo,
      concept_id: conceptId,
      isbn: isbn,
      modelo: modelo,
      tipo_cliente: tipo,
      created_at: new Date().toISOString()
    });
    bumpCliente(state, tipo, correo);
    saveState(state);
    return envelope(
      "    <tns:RegistrarClasificacionResponse>\n" +
        "      <tns:clasificacionId>" + id + "</tns:clasificacionId>\n" +
        "      <tns:mensaje>Clasificación registrada</tns:mensaje>\n" +
        "      <tns:modelo>" + escapeXml(modelo) + "</tns:modelo>\n" +
        "      <tns:fecha>" + escapeXml(new Date().toISOString()) + "</tns:fecha>\n" +
        "    </tns:RegistrarClasificacionResponse>"
    );
  }

  function progreso(payload) {
    var correo = requireEmail(payload);
    var state = loadState();
    var done = state.clasificaciones.filter(function (row) { return row.correo === correo; }).length;
    var persona = state.clasificadores[correo];
    var nombre = persona ? persona.nombre + " " + persona.apellidos : "Sin registros";
    return envelope(
      "    <tns:ObtenerProgresoUsuarioResponse>\n" +
        "      <tns:correo>" + escapeXml(correo) + "</tns:correo>\n" +
        "      <tns:nombreCompleto>" + escapeXml(nombre) + "</tns:nombreCompleto>\n" +
        "      <tns:clasificados>" + done + "</tns:clasificados>\n" +
        "      <tns:pendientes>" + Math.max(CATALOGO.length - done, 0) + "</tns:pendientes>\n" +
        "      <tns:totalCatalogo>" + CATALOGO.length + "</tns:totalCatalogo>\n" +
        "    </tns:ObtenerProgresoUsuarioResponse>"
    );
  }

  function estadisticas() {
    var state = loadState();
    var counts = { IaaS: 0, PaaS: 0, SaaS: 0, FaaS: 0 };
    state.clasificaciones.forEach(function (row) {
      counts[row.modelo] = (counts[row.modelo] || 0) + 1;
    });
    var inner = MODELS.map(function (modelo) {
      return (
        "      <tns:item>\n" +
        "        <tns:modelo>" + modelo + "</tns:modelo>\n" +
        "        <tns:cantidad>" + counts[modelo] + "</tns:cantidad>\n" +
        "      </tns:item>"
      );
    }).join("\n");
    return envelope(
      "    <tns:ObtenerEstadisticasPorModeloResponse>\n" + inner +
        "\n    </tns:ObtenerEstadisticasPorModeloResponse>"
    );
  }

  function bumpCliente(state, tipo, identificador) {
    var actual = state.clientes[tipo] || { peticiones: 0, identificador: identificador };
    actual.peticiones += 1;
    actual.identificador = identificador;
    actual.ultima_peticion = new Date().toISOString();
    state.clientes[tipo] = actual;
  }

  function buildPendientes(correo, tipo) {
    return envelope(
      "    <tns:ObtenerConceptosPendientes>\n" +
        "      <tns:correo>" + escapeXml(correo) + "</tns:correo>\n" +
        "      <tns:tipoCliente>" + escapeXml(tipo || "desktop-web") + "</tns:tipoCliente>\n" +
        "    </tns:ObtenerConceptosPendientes>"
    );
  }

  function buildRegistrar(fields) {
    return envelope(
      "    <tns:RegistrarClasificacion>\n" +
        "      <tns:nombre>" + escapeXml(fields.nombre) + "</tns:nombre>\n" +
        "      <tns:apellidos>" + escapeXml(fields.apellidos) + "</tns:apellidos>\n" +
        "      <tns:correo>" + escapeXml(fields.correo) + "</tns:correo>\n" +
        "      <tns:conceptId>" + escapeXml(fields.conceptId) + "</tns:conceptId>\n" +
        "      <tns:isbn>" + escapeXml(fields.isbn) + "</tns:isbn>\n" +
        "      <tns:modelo>" + escapeXml(fields.modelo) + "</tns:modelo>\n" +
        "      <tns:tipoCliente>" + escapeXml(fields.tipoCliente || "desktop-web") + "</tns:tipoCliente>\n" +
        "    </tns:RegistrarClasificacion>"
    );
  }

  function buildProgreso(correo) {
    return envelope(
      "    <tns:ObtenerProgresoUsuario>\n" +
        "      <tns:correo>" + escapeXml(correo) + "</tns:correo>\n" +
        "    </tns:ObtenerProgresoUsuario>"
    );
  }

  function buildEstadisticas(user, pass) {
    return envelope(
      "    <tns:ObtenerEstadisticasPorModelo/>",
      securityHeader(user, pass)
    );
  }

  function invoke(xmlText) {
    try {
      return { ok: true, xml: handleRequest(xmlText) };
    } catch (err) {
      if (err && err.fault) return { ok: false, xml: err.xml };
      return {
        ok: false,
        xml: faultXml("Server", 500, "ServerFault", "El servicio no pudo completar la operación. Intenta de nuevo más tarde.")
      };
    }
  }

  function pretty(xml) {
    return xml.replace(/\n+$/, "") + "\n";
  }

  function catalog() {
    return CATALOGO.slice();
  }

  function reset() {
    localStorage.removeItem(STORAGE_KEY);
  }

  global.SoapModulo = {
    invoke: invoke,
    pretty: pretty,
    catalog: catalog,
    reset: reset,
    buildPendientes: buildPendientes,
    buildRegistrar: buildRegistrar,
    buildProgreso: buildProgreso,
    buildEstadisticas: buildEstadisticas,
    faultXml: faultXml,
    STATS_USER: STATS_USER,
    MODELS: MODELS
  };
})(window);
