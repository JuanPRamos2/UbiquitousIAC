/**
 * Utilidad de serialización dual JSON y XML.
 * Inspecciona la cabecera 'Accept' y el parámetro '?format=xml'.
 * Por defecto serializa en JSON; si se solicita XML, envuelve la respuesta
 * con etiqueta raíz <catalogo>...</catalogo> y cabecera application/xml.
 */

function escaparXml(valor) {
  if (valor === null || valor === undefined) return "";
  const str = valor instanceof Date ? valor.toISOString() : String(valor);
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function sanitizarEtiqueta(nombre) {
  if (!nombre || typeof nombre !== "string") return "item";
  const limpia = nombre.replace(/[^a-zA-Z0-9_\-]/g, "_");
  return /^[a-zA-Z_]/.test(limpia) ? limpia : `item_${limpia}`;
}

export function convertirAXml(datos, etiqueta = "item") {
  const tag = sanitizarEtiqueta(etiqueta);
  if (datos === null || datos === undefined) {
    return `<${tag}></${tag}>`;
  }
  if (typeof datos === "boolean" || typeof datos === "number" || typeof datos === "string" || datos instanceof Date) {
    return `<${tag}>${escaparXml(datos)}</${tag}>`;
  }
  if (Array.isArray(datos)) {
    if (datos.length === 0) {
      return `<${tag}></${tag}>`;
    }
    const elementos = datos.map((elem) => convertirAXml(elem, "item")).join("");
    return `<${tag}>${elementos}</${tag}>`;
  }
  if (typeof datos === "object") {
    const hijos = Object.entries(datos)
      .map(([clave, valor]) => {
        if (Array.isArray(valor)) {
          const subItems = valor.map((item) => convertirAXml(item, "item")).join("");
          return `<${sanitizarEtiqueta(clave)}>${subItems}</${sanitizarEtiqueta(clave)}>`;
        }
        return convertirAXml(valor, clave);
      })
      .join("");
    return `<${tag}>${hijos}</${tag}>`;
  }
  return `<${tag}>${escaparXml(datos)}</${tag}>`;
}

export function generarXml(datos, rootTag = "catalogo") {
  const tagRaiz = sanitizarEtiqueta(rootTag);
  let cuerpo = "";
  if (datos === null || datos === undefined) {
    cuerpo = "";
  } else if (typeof datos === "object" && !Array.isArray(datos)) {
    cuerpo = Object.entries(datos)
      .map(([clave, valor]) => {
        if (Array.isArray(valor)) {
          const subItems = valor.map((item) => convertirAXml(item, "item")).join("");
          return `<${sanitizarEtiqueta(clave)}>${subItems}</${sanitizarEtiqueta(clave)}>`;
        }
        return convertirAXml(valor, clave);
      })
      .join("");
  } else if (Array.isArray(datos)) {
    cuerpo = datos.map((item) => convertirAXml(item, "item")).join("");
  } else {
    cuerpo = escaparXml(datos);
  }
  return `<?xml version="1.0" encoding="UTF-8"?>\n<${tagRaiz} xmlns="http://nexum.com.mx/bienestar/v1">${cuerpo}</${tagRaiz}>`;
}

export function solicitaXml(req) {
  if (!req) return false;
  const formatQuery = (req.query?.format || "").toLowerCase();
  if (formatQuery === "xml") return true;
  const acceptHeader = (req.headers?.accept || req.headers?.Accept || "").toLowerCase();
  return acceptHeader.includes("application/xml") || acceptHeader.includes("text/xml");
}

export function responderCatalogo(req, res, datos, { rootTag = "catalogo", status = 200 } = {}) {
  if (solicitaXml(req)) {
    res.status(status);
    res.set("Content-Type", "application/xml; charset=utf-8");
    return res.send(generarXml(datos, rootTag));
  }
  return res.status(status).json(datos);
}
