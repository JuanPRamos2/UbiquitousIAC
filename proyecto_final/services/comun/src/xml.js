import { XMLBuilder, XMLParser } from "fast-xml-parser";
import { HttpError } from "./errores.js";

const ITEMS = {
  campanias: "campania",
  unidades: "unidad",
  instrumentos: "instrumento",
  fuentes: "fuente",
  intervenciones: "intervencion",
  eventos: "evento",
  resultados: "resultado",
  presupuestos: "presupuesto",
  solicitudes: "solicitud",
  categories: "category",
  series: "serie",
  reactivos: "reactivo",
  dimensiones: "dimension",
};

const parser = new XMLParser({
  ignoreAttributes: true,
  trimValues: true,
  parseTagValue: false,
  processEntities: false,
});

const builder = new XMLBuilder({
  ignoreAttributes: true,
  format: true,
  suppressEmptyNode: false,
  processEntities: true,
});

function primitivo(valor) {
  if (valor === null || valor === undefined) return "";
  if (valor instanceof Date) return valor.toISOString();
  if (typeof valor === "boolean") return valor ? "true" : "false";
  return valor;
}

function nombreItem(clave, padre) {
  if (clave === "data" && (padre === "serie" || padre === "series")) return "point";
  if (ITEMS[clave]) return ITEMS[clave];
  return "item";
}

function transformar(valor, padre) {
  if (Array.isArray(valor)) {
    return valor.map((item) => (item && typeof item === "object" ? transformar(item, padre) : primitivo(item)));
  }
  if (valor && typeof valor === "object" && !(valor instanceof Date)) {
    const salida = {};
    for (const [clave, item] of Object.entries(valor)) {
      if (item === undefined) continue;
      if (Array.isArray(item)) {
        if (item.length === 0) {
          salida[clave] = "";
          continue;
        }
        const etiqueta = nombreItem(clave, padre);
        salida[clave] = {
          [etiqueta]: item.map((elemento) =>
            elemento && typeof elemento === "object" ? transformar(elemento, clave) : primitivo(elemento)
          ),
        };
        continue;
      }
      salida[clave] = item && typeof item === "object" ? transformar(item, clave) : primitivo(item);
    }
    return salida;
  }
  return primitivo(valor);
}

export function aXml(envelope) {
  const cuerpo = builder.build({ response: transformar(envelope, "response") });
  return `<?xml version="1.0" encoding="UTF-8"?>\n${cuerpo}`;
}

export function parsearXml(texto) {
  const crudo = String(texto || "").trim();
  if (!crudo.startsWith("<")) {
    throw new HttpError(400, "XML_MAL_FORMADO", "El cuerpo no es XML");
  }
  let documento;
  try {
    documento = parser.parse(crudo);
  } catch {
    throw new HttpError(400, "XML_MAL_FORMADO", "El XML no se pudo leer");
  }
  const raiz = documento.busqueda || documento.reporte || documento.response;
  if (!raiz || typeof raiz !== "object") {
    throw new HttpError(400, "XML_MAL_FORMADO", "El XML no tiene un elemento raíz reconocido");
  }
  return raiz;
}

export function quiereXml(req) {
  const formato = String(req.query?.format || "").toLowerCase();
  if (formato === "xml") return true;
  if (formato === "json") return false;
  const accept = String(req.headers?.accept || "");
  return accept.includes("application/xml") || accept.includes("text/xml");
}
