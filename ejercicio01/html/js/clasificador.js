/**
 * Misma lógica que el clasificador Java (Regex + NLP).
 * Corre en el navegador para que el ejercicio funcione en ubiquitous.
 */
(function (global) {
  "use strict";

  var MODELS = {
    IAAS: { acronym: "IaaS", fullName: "Infrastructure as a Service", color: "#4d6b8a",
      description: "El proveedor ofrece recursos de infraestructura: máquinas virtuales, redes y almacenamiento." },
    PAAS: { acronym: "PaaS", fullName: "Platform as a Service", color: "#5c7a68",
      description: "El proveedor ofrece una plataforma para desplegar aplicaciones sin administrar servidores." },
    SAAS: { acronym: "SaaS", fullName: "Software as a Service", color: "#8a6a4a",
      description: "El usuario consume software listo a través de internet, normalmente con una suscripción." },
    FAAS: { acronym: "FaaS", fullName: "Function as a Service", color: "#6b5a7a",
      description: "Se ejecutan funciones pequeñas en respuesta a eventos, sin mantener servidores encendidos." },
    INDETERMINADO: { acronym: "Indeterminado", fullName: "No clasificado", color: "#6a635a",
      description: "El texto no contiene evidencia suficiente o varios modelos empataron." }
  };

  var STOPWORDS = {
    el: 1, la: 1, los: 1, las: 1, un: 1, una: 1, unos: 1, unas: 1, de: 1, del: 1, al: 1, a: 1,
    y: 1, o: 1, u: 1, en: 1, por: 1, para: 1, con: 1, sin: 1, ni: 1, que: 1, se: 1, su: 1, sus: 1,
    mi: 1, mis: 1, tu: 1, tus: 1, lo: 1, le: 1, les: 1, es: 1, son: 1, ser: 1, como: 1, mas: 1,
    más: 1, cuando: 1, donde: 1, qué: 1, cual: 1, cuál: 1, este: 1, esta: 1, estos: 1, estas: 1,
    eso: 1, esa: 1, me: 1, te: 1, nos: 1, ya: 1, muy: 1, pero: 1, si: 1, sí: 1, no: 1, también: 1,
    the: 1, an: 1, of: 1, to: 1, and: 1, or: 1, for: 1, with: 1, from: 1, on: 1, in: 1, at: 1,
    my: 1, your: 1, our: 1, is: 1, are: 1, be: 1, when: 1, that: 1, this: 1, it: 1,
    necesito: 1, quiero: 1, puedo: 1, puede: 1, pueden: 1, utilizar: 1, utilizan: 1, usar: 1,
    tengo: 1, tiene: 1, hacen: 1, hacer: 1, desde: 1, cada: 1, vez: 1, propio: 1, propia: 1
  };

  var IAAS_STEMS = ["maquina", "virtual", "vm", "ec2", "vpc", "infraestructur", "instancia",
    "almacen", "disco", "red", "hardware", "cpu", "ram", "linux", "compute", "virtualiz"];
  var PAAS_STEMS = ["despleg", "plataforma", "heroku", "runtime", "beanstalk", "paas",
    "framework", "pipeline", "buildpack"];
  var SAAS_STEMS = ["correo", "gmail", "dropbox", "salesforce", "outlook", "suscrip",
    "navegador", "office", "docs", "saas", "software"];
  var FAAS_STEMS = ["funcion", "lambda", "serverless", "evento", "trigger", "faas",
    "automatic", "webhook"];

  var IAAS_PATTERNS = [
    /maquinas?\s+virtuales?/iu,
    /\b(vm|ec2|vpc)\b/iu,
    /compute\s+engine/iu,
    /azure\s+vm/iu,
    /sistema\s+operativo/iu,
    /\b(infraestructura|instancias?|virtualizacion|hardware)\b/iu,
    /\b(almacenamiento|discos?|cpu|ram)\b/iu,
    /\bredes?\b/iu,
    /\bservidores?\b/iu
  ];
  var PAAS_PATTERNS = [
    /despleg(ar|ando|ue)?/iu,
    /sin\s+administrar/iu,
    /no\s+administrar/iu,
    /aplicacion\s+web/iu,
    /app\s+engine/iu,
    /azure\s+app/iu,
    /\b(heroku|plataforma|runtime|beanstalk)\b/iu,
    /entorno\s+de\s+(desarrollo|ejecucion)/iu
  ];
  var SAAS_PATTERNS = [
    /correo\s+electronico/iu,
    /\b(gmail|dropbox|salesforce|outlook)\b/iu,
    /google\s+docs/iu,
    /office\s*365/iu,
    /\b(suscripcion|navegador)\b/iu,
    /desde\s+el\s+navegador/iu,
    /software\s+(listo|como\s+servicio)/iu,
    /empleados\s+utilizan/iu
  ];
  var FAAS_PATTERNS = [
    /ejecutar\s+una\s+funcion/iu,
    /\bfunciones?\b/iu,
    /\b(lambda|serverless)\b/iu,
    /cloud\s+functions?/iu,
    /azure\s+functions?/iu,
    /cada\s+vez\s+que/iu,
    /en\s+respuesta\s+a/iu,
    /\b(automaticamente|evento|trigger)\b/iu,
    /suba\s+una\s+imagen/iu
  ];

  function stripAccents(text) {
    return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  }

  function replaceSuffix(word, suffix, replacement) {
    if (word.endsWith(suffix) && word.length - suffix.length >= 3) {
      return word.slice(0, -suffix.length) + replacement;
    }
    return word;
  }

  function stemSpanish(token) {
    var word = token;
    if (word.length <= 3) {
      return word;
    }
    word = replaceSuffix(word, "aciones", "ar");
    word = replaceSuffix(word, "iciones", "ir");
    word = replaceSuffix(word, "amente", "");
    word = replaceSuffix(word, "mente", "");
    word = replaceSuffix(word, "acion", "");
    word = replaceSuffix(word, "cion", "");
    word = replaceSuffix(word, "sion", "");
    word = replaceSuffix(word, "ando", "");
    word = replaceSuffix(word, "iendo", "");
    if (word.endsWith("es") && word.length > 4) {
      word = word.slice(0, -2);
    } else if (word.endsWith("s") && word.length > 3 && !word.endsWith("us") && !word.endsWith("is")) {
      word = word.slice(0, -1);
    }
    if (word.length > 4 && (word.endsWith("ar") || word.endsWith("er") || word.endsWith("ir"))) {
      word = word.slice(0, -2);
    }
    return word;
  }

  function processText(rawText) {
    var lower = rawText.toLowerCase();
    var normalized = stripAccents(lower);
    var cleaned = normalized.replace(/[^a-z0-9\s]/g, " ").replace(/\s+/g, " ").trim();
    var tokens = cleaned ? cleaned.split(" ") : [];
    var withoutStopwords = tokens.filter(function (token) {
      return token.length > 1 && !STOPWORDS[token];
    });
    var stems = withoutStopwords.map(stemSpanish);
    return {
      original: rawText,
      lowercased: lower,
      normalized: normalized,
      cleaned: cleaned,
      tokens: tokens,
      withoutStopwords: withoutStopwords,
      stems: stems,
      containsStem: function (stem) { return stems.indexOf(stem) !== -1; },
      joinedStems: function () { return stems.join(" "); }
    };
  }

  function matchPatterns(text, patterns, weight) {
    var matches = [];
    var score = 0;
    patterns.forEach(function (pattern) {
      var copy = new RegExp(pattern.source, pattern.flags);
      var found = copy.exec(text);
      if (found) {
        matches.push(found[0]);
        score += weight;
      }
    });
    return { score: score, matches: matches };
  }

  function plusDetail(detail, label, extra) {
    return { score: detail.score + extra, matches: detail.matches.concat([label]) };
  }

  function withoutContaining(detail, fragments) {
    var filtered = [];
    var removed = 0;
    detail.matches.forEach(function (match) {
      var lower = match.toLowerCase();
      var drop = fragments.some(function (fragment) { return lower.indexOf(fragment) !== -1; });
      if (drop) {
        removed += 1;
      } else {
        filtered.push(match);
      }
    });
    return { score: Math.max(0, detail.score - removed * 2), matches: filtered };
  }

  function avoidsManaging(text) {
    return /sin\s+administrar|no\s+administrar/iu.test(text);
  }

  function pickWinner(scores) {
    var keys = ["IAAS", "PAAS", "SAAS", "FAAS"];
    var max = 0;
    keys.forEach(function (key) {
      if (scores[key] > max) {
        max = scores[key];
      }
    });
    if (max === 0) {
      return "INDETERMINADO";
    }
    var ties = keys.filter(function (key) { return scores[key] === max; });
    return ties.length > 1 ? "INDETERMINADO" : ties[0];
  }

  function classifyRegex(fullName, text) {
    var normalized = stripAccents(text);
    var iaas = matchPatterns(normalized, IAAS_PATTERNS, 2);
    if (avoidsManaging(normalized)) {
      iaas = withoutContaining(iaas, ["servidor", "sistema operativo", "redes"]);
    }
    var paas = matchPatterns(normalized, PAAS_PATTERNS, 3);
    if (avoidsManaging(normalized)) {
      paas = plusDetail(paas, "sin administrar infraestructura", 3);
    }
    var saas = matchPatterns(normalized, SAAS_PATTERNS, 3);
    var faas = matchPatterns(normalized, FAAS_PATTERNS, 3);
    var scores = { IAAS: iaas.score, PAAS: paas.score, SAAS: saas.score, FAAS: faas.score };
    var winner = pickWinner(scores);
    var explanation;
    if (winner === "INDETERMINADO" && scores.IAAS + scores.PAAS + scores.SAAS + scores.FAAS === 0) {
      explanation = "No se encontraron palabras clave ni patrones suficientes.";
    } else {
      explanation = (winner === "INDETERMINADO"
        ? "Hay empate entre dos o más modelos. Revisa las coincidencias."
        : "Predomina " + MODELS[winner].acronym + " porque acumuló más coincidencias.") +
        "\nIaaS: " + formatDetail(iaas) +
        "\nPaaS: " + formatDetail(paas) +
        "\nSaaS: " + formatDetail(saas) +
        "\nFaaS: " + formatDetail(faas);
    }
    return result(fullName, text, winner, scores, explanation, "Regex + palabras clave");
  }

  function formatDetail(detail) {
    if (!detail.matches.length) {
      return detail.score + " pts (sin coincidencias)";
    }
    return detail.score + " pts — " + detail.matches.join(", ");
  }

  function scoreStems(processed, categoryStems) {
    var hits = [];
    var score = 0;
    processed.stems.forEach(function (stem) {
      categoryStems.forEach(function (expected) {
        if (stem === expected || stem.indexOf(expected) === 0 ||
            (expected.indexOf(stem) === 0 && stem.length >= 4)) {
          if (hits.indexOf(stem) === -1) {
            hits.push(stem);
            score += 2;
          }
        }
      });
    });
    return { score: score, evidence: hits };
  }

  function addPhrase(current, processed, phrase, weight) {
    var haystack = processed.cleaned + " " + processed.joinedStems();
    if (haystack.indexOf(stripAccents(phrase)) !== -1) {
      return { score: current.score + weight, evidence: current.evidence.concat([phrase]) };
    }
    return current;
  }

  function classifyNlp(fullName, text) {
    var processed = processText(text);
    var iaas = scoreStems(processed, IAAS_STEMS);
    iaas = addPhrase(iaas, processed, "maquina virtual", 4);
    iaas = addPhrase(iaas, processed, "sistema operativo", 3);
    iaas = addPhrase(iaas, processed, "compute engine", 4);
    if (avoidsManaging(processed.cleaned)) {
      iaas = withoutContaining({ score: iaas.score, matches: iaas.evidence }, ["servidor", "operativo"]);
      iaas = { score: iaas.score, evidence: iaas.matches };
    } else if (processed.containsStem("servidor") || processed.joinedStems().indexOf("servidor") !== -1) {
      iaas = { score: iaas.score + 2, evidence: iaas.evidence.concat(["servidor"]) };
    }

    var paas = scoreStems(processed, PAAS_STEMS);
    paas = addPhrase(paas, processed, "app engine", 4);
    paas = addPhrase(paas, processed, "aplicacion web", 2);
    paas = addPhrase(paas, processed, "azure app", 3);
    if (avoidsManaging(processed.cleaned)) {
      paas = { score: paas.score + 4, evidence: paas.evidence.concat(["no administrar servidores/SO"]) };
    }

    var saas = scoreStems(processed, SAAS_STEMS);
    saas = addPhrase(saas, processed, "correo electronico", 4);
    saas = addPhrase(saas, processed, "google docs", 4);
    saas = addPhrase(saas, processed, "office 365", 4);

    var faas = scoreStems(processed, FAAS_STEMS);
    faas = addPhrase(faas, processed, "ejecut funcion", 4);
    faas = addPhrase(faas, processed, "cloud function", 4);
    faas = addPhrase(faas, processed, "azure function", 4);
    if (processed.cleaned.indexOf("suba") !== -1 || processed.containsStem("sub")) {
      faas = { score: faas.score + 3, evidence: faas.evidence.concat(["evento al subir archivo"]) };
    }

    var scores = { IAAS: iaas.score, PAAS: paas.score, SAAS: saas.score, FAAS: faas.score };
    var winner = pickWinner(scores);
    var explanation =
      "Pipeline NLP: minúsculas → limpieza → tokens → stopwords → stems.\n" +
      "Tokens: " + processed.tokens.join(", ") + "\n" +
      "Stems: " + processed.stems.join(", ") + "\n" +
      (winner === "INDETERMINADO" ? "No hay un modelo predominante.\n" : "Predomina " + MODELS[winner].acronym + " por puntuación.\n") +
      "IaaS: " + nlpLine(iaas) + "\nPaaS: " + nlpLine(paas) +
      "\nSaaS: " + nlpLine(saas) + "\nFaaS: " + nlpLine(faas);
    return result(fullName, text, winner, scores, explanation, "NLP básico + puntuaciones");
  }

  function nlpLine(detail) {
    if (!detail.evidence.length) {
      return detail.score + " pts";
    }
    return detail.score + " pts — " + detail.evidence.join(", ");
  }

  function result(fullName, text, winner, scores, explanation, engine) {
    return {
      fullUserName: fullName,
      originalText: text,
      model: MODELS[winner],
      modelKey: winner,
      scores: scores,
      explanation: explanation,
      engineName: engine
    };
  }

  function validate(firstName, lastName, description) {
    var nameRe = /^[\p{L}]+([ '\-][\p{L}]+)*$/u;
    function checkName(value, label) {
      var trimmed = (value || "").trim();
      if (!trimmed) {
        throw new Error('El campo "' + label + '" no puede estar vacío.');
      }
      if (trimmed.length < 2) {
        throw new Error('El campo "' + label + '" es demasiado corto.');
      }
      if (trimmed.length > 40) {
        throw new Error('El campo "' + label + '" es demasiado largo.');
      }
      if (!nameRe.test(trimmed)) {
        throw new Error('El campo "' + label + '" solo admite letras, espacios, apóstrofos o guiones.');
      }
      return trimmed;
    }
    var text = (description || "").trim();
    if (!text) {
      throw new Error("La descripción del servicio Cloud no puede estar vacía.");
    }
    if (text.length < 8) {
      throw new Error("Escribe una descripción más completa (mínimo 8 caracteres).");
    }
    return {
      firstName: checkName(firstName, "Nombre"),
      lastName: checkName(lastName, "Apellido"),
      description: text
    };
  }

  function classify(firstName, lastName, description, engine) {
    var input = validate(firstName, lastName, description);
    var fullName = input.firstName + " " + input.lastName;
    if (engine === "regex") {
      return classifyRegex(fullName, input.description);
    }
    return classifyNlp(fullName, input.description);
  }

  global.CloudClassifier = {
    MODELS: MODELS,
    classify: classify,
    examples: [
      {
        label: "Ejemplo IaaS",
        text: "Necesito máquinas virtuales, almacenamiento y redes configurables para instalar mi propio sistema operativo."
      },
      {
        label: "Ejemplo PaaS",
        text: "Quiero desplegar mi aplicación web sin administrar directamente servidores ni sistemas operativos."
      },
      {
        label: "Ejemplo SaaS",
        text: "Los empleados utilizan una aplicación de correo electrónico directamente desde el navegador y pagan una suscripción mensual."
      },
      {
        label: "Ejemplo FaaS",
        text: "Necesito ejecutar una función automáticamente cada vez que un usuario suba una imagen al almacenamiento Cloud."
      }
    ]
  };
})(window);
