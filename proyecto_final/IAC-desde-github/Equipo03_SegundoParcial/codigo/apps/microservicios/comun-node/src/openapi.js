/**
 * Documentacion OpenAPI servida por cada microservicio en Node.
 *
 * Expone, igual que los servicios en Python:
 *     GET /openapi.json   el contrato
 *     GET /docs           Swagger UI
 *
 * Swagger UI se sirve desde el propio servicio y no desde un CDN. Si la
 * red de la demostracion bloquea el CDN, la documentacion igual abre: eso
 * ya paso una vez durante el desarrollo y costo una tarde.
 *
 * El contrato se escribe en openapi.yaml junto al servicio y se convierte
 * a JSON aqui, sin depender de ninguna biblioteca de YAML externa: el
 * subconjunto que usamos (mapas, listas, cadenas, numeros, booleanos y
 * bloques literales) se cubre con un analizador de 60 lineas y una
 * dependencia menos es una superficie de ataque menos.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const SWAGGER = path.join(AQUI, "estaticos", "swagger");

/** Analizador del subconjunto de YAML que usan los contratos del proyecto. */
export function yamlAObjeto(texto) {
  const lineas = texto.split(/\r?\n/);
  const raiz = {};
  // pila de contextos: { sangria, contenedor, claveLista }
  const pila = [{ sangria: -1, nodo: raiz }];
  let i = 0;

  const valorEscalar = (s) => {
    const v = s.trim();
    if (v === "" || v === "~" || v === "null") return null;
    if (v === "true") return true;
    if (v === "false") return false;
    if (/^-?\d+$/.test(v)) return Number(v);
    if (/^-?\d*\.\d+$/.test(v)) return Number(v);
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) {
      return v.slice(1, -1).replace(/\\n/g, "\n").replace(/''/g, "'");
    }
    if (v.startsWith("[") && v.endsWith("]")) {
      const dentro = v.slice(1, -1).trim();
      return dentro ? dentro.split(",").map((x) => valorEscalar(x)) : [];
    }
    if (v.startsWith("{") && v.endsWith("}")) {
      const dentro = v.slice(1, -1).trim();
      const o = {};
      if (dentro) {
        for (const par of dentro.split(",")) {
          const k = par.slice(0, par.indexOf(":")).trim();
          o[valorEscalar(k)] = valorEscalar(par.slice(par.indexOf(":") + 1));
        }
      }
      return o;
    }
    return v;
  };

  const cima = (sangria) => {
    while (pila.length > 1 && pila[pila.length - 1].sangria >= sangria) pila.pop();
    return pila[pila.length - 1].nodo;
  };

  while (i < lineas.length) {
    const linea = lineas[i];
    if (!linea.trim() || linea.trim().startsWith("#")) { i++; continue; }
    const sangria = linea.length - linea.trimStart().length;
    const contenido = linea.trim();

    // elemento de lista
    if (contenido.startsWith("- ")) {
      const padre = cima(sangria);
      const arreglo = Array.isArray(padre) ? padre : null;
      const resto = contenido.slice(2).trim();
      if (!arreglo) { i++; continue; }
      if (resto.includes(":") && !resto.startsWith("{")) {
        const nodo = {};
        arreglo.push(nodo);
        pila.push({ sangria, nodo });
        const k = resto.slice(0, resto.indexOf(":")).trim();
        const v = resto.slice(resto.indexOf(":") + 1).trim();
        if (v) nodo[k] = valorEscalar(v);
        else { const hijo = {}; nodo[k] = hijo; pila.push({ sangria: sangria + 2, nodo: hijo }); }
      } else {
        arreglo.push(valorEscalar(resto));
      }
      i++; continue;
    }

    const dosPuntos = contenido.indexOf(":");
    if (dosPuntos < 0) { i++; continue; }
    const clave = valorEscalar(contenido.slice(0, dosPuntos));
    let resto = contenido.slice(dosPuntos + 1).trim();
    const padre = cima(sangria);
    if (Array.isArray(padre)) { i++; continue; }

    if (resto === "|" || resto === ">" || resto === "|-" || resto === ">-") {
      const bloque = [];
      let j = i + 1;
      while (j < lineas.length) {
        const l = lineas[j];
        if (l.trim() && (l.length - l.trimStart().length) <= sangria) break;
        bloque.push(l.slice(Math.min(sangria + 2, l.length - l.trimStart().length || sangria + 2)));
        j++;
      }
      padre[clave] = resto.startsWith("|") ? bloque.join("\n") : bloque.join(" ").trim();
      i = j; continue;
    }

    if (resto === "") {
      // ¿lo que sigue es una lista o un mapa?
      let j = i + 1;
      while (j < lineas.length && (!lineas[j].trim() || lineas[j].trim().startsWith("#"))) j++;
      const siguiente = lineas[j];
      const sangriaSig = siguiente ? siguiente.length - siguiente.trimStart().length : -1;
      if (siguiente && sangriaSig > sangria && siguiente.trim().startsWith("- ")) {
        const arr = [];
        padre[clave] = arr;
        pila.push({ sangria, nodo: arr });
      } else if (siguiente && sangriaSig > sangria) {
        const nodo = {};
        padre[clave] = nodo;
        pila.push({ sangria, nodo });
      } else {
        padre[clave] = null;
      }
      i++; continue;
    }

    padre[clave] = valorEscalar(resto);
    i++;
  }
  return raiz;
}

export function leerContrato(rutaYaml) {
  const ruta = rutaYaml instanceof URL ? fileURLToPath(rutaYaml) : rutaYaml;
  return yamlAObjeto(fs.readFileSync(ruta, "utf8"));
}

const PAGINA = (nombre) => `<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>${nombre} — Bienestar Nexum</title>
<link rel="stylesheet" href="/docs/estaticos/swagger-ui.css">
<style>body{margin:0}.topbar{display:none}</style>
</head><body>
<div id="swagger"></div>
<script src="/docs/estaticos/swagger-ui-bundle.js"></script>
<script>
SwaggerUIBundle({url:"/openapi.json",dom_id:"#swagger",deepLinking:true,
  docExpansion:"list",defaultModelsExpandDepth:1,tryItOutEnabled:true});
</script>
</body></html>`;

export const RESPUESTAS_COMUNES_OPENAPI = {
  SolicitudInvalida: {
    description: "Parametro mal formado o invalido.",
    content: {
      "application/json": { schema: { $ref: "#/components/schemas/Error" } },
      "application/xml": { schema: { $ref: "#/components/schemas/Error" } },
    },
  },
  NoAutenticado: {
    description: "Falta el token, es invalido, expiro o la sesion fue revocada.",
    content: {
      "application/json": { schema: { $ref: "#/components/schemas/Error" } },
      "application/xml": { schema: { $ref: "#/components/schemas/Error" } },
    },
  },
  SinPermiso: {
    description: "El perfil no tiene el permiso necesario.",
    content: {
      "application/json": { schema: { $ref: "#/components/schemas/Error" } },
      "application/xml": { schema: { $ref: "#/components/schemas/Error" } },
    },
  },
  NoEncontrado: {
    description: "El recurso solicitado no existe.",
    content: {
      "application/json": { schema: { $ref: "#/components/schemas/Error" } },
      "application/xml": { schema: { $ref: "#/components/schemas/Error" } },
    },
  },
  ValidacionFallida: {
    description: "La solicitud trae campos invalidos.",
    content: {
      "application/json": { schema: { $ref: "#/components/schemas/Error" } },
      "application/xml": { schema: { $ref: "#/components/schemas/Error" } },
    },
  },
  LimiteExcedido: {
    description: "Se rebaso el limite de consumo.",
    content: {
      "application/json": { schema: { $ref: "#/components/schemas/Error" } },
      "application/xml": { schema: { $ref: "#/components/schemas/Error" } },
    },
  },
  ErrorInterno: {
    description: "Falla no prevista del servicio.",
    content: {
      "application/json": { schema: { $ref: "#/components/schemas/Error" } },
      "application/xml": { schema: { $ref: "#/components/schemas/Error" } },
    },
  },
};

export const ESQUEMA_ERROR_BASE = {
  type: "object",
  required: ["error"],
  properties: {
    error: {
      type: "object",
      required: ["codigo", "mensaje", "detalles", "correlacion_id"],
      properties: {
        codigo: { type: "string" },
        mensaje: { type: "string" },
        detalles: { type: "array", items: { type: "object" } },
        correlacion_id: { type: "string" },
      },
    },
  },
};

export function crearContratoOpenApi({ nombre, version = "1.0.0", descripcion = "", rutas = {}, esquemas = {} }) {
  return {
    openapi: "3.0.3",
    info: {
      title: `${nombre} — Bienestar Nexum`,
      version,
      description: descripcion,
    },
    paths: rutas,
    components: {
      securitySchemes: {
        bearerAuth: {
          type: "http",
          scheme: "bearer",
          bearerFormat: "JWT",
          description: "Token JWT emitido por auth-service.",
        },
      },
      schemas: {
        Error: ESQUEMA_ERROR_BASE,
        ...esquemas,
      },
      responses: RESPUESTAS_COMUNES_OPENAPI,
    },
  };
}

/** Monta /openapi.json, /docs y los estaticos de Swagger UI. */
export function montarSwagger(app, nombre, rutaYamlOContrato) {
  let contrato = null;
  app.get("/openapi.json", (req, res) => {
    try {
      if (!contrato) {
        if (typeof rutaYamlOContrato === "object" && !(rutaYamlOContrato instanceof URL)) {
          contrato = rutaYamlOContrato;
        } else {
          contrato = leerContrato(rutaYamlOContrato);
        }
      }
      res.json(contrato);
    } catch (e) {
      res.status(500).json({ error: { codigo: "CONTRATO_ILEGIBLE",
        mensaje: String(e.message || e), detalles: [], correlacion_id: req.correlacionId || "" } });
    }
  });
  app.get("/docs", (req, res) => res.type("html").send(PAGINA(nombre)));
  app.get("/docs/estaticos/:archivo", (req, res) => {
    const permitidos = new Set(["swagger-ui.css", "swagger-ui-bundle.js"]);
    if (!permitidos.has(req.params.archivo)) return res.status(404).end();
    res.type(req.params.archivo.endsWith(".css") ? "text/css" : "application/javascript");
    res.send(fs.readFileSync(path.join(SWAGGER, req.params.archivo)));
  });
}
