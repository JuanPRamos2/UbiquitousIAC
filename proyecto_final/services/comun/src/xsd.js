import { existsSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { XMLParser } from "fast-xml-parser";
import { HttpError } from "./errores.js";

const parserXsd = new XMLParser({
  ignoreAttributes: false,
  attributeNamePrefix: "@_",
  removeNSPrefix: true,
  trimValues: true,
  parseTagValue: false,
});

const parserXml = new XMLParser({
  ignoreAttributes: true,
  trimValues: true,
  parseTagValue: false,
  processEntities: false,
});

function lista(valor) {
  if (valor === undefined || valor === null || valor === "") return [];
  return Array.isArray(valor) ? valor : [valor];
}

function tipoLocal(tipo) {
  if (!tipo) return "";
  const texto = String(tipo);
  const corte = texto.lastIndexOf(":");
  return corte >= 0 ? texto.slice(corte + 1) : texto;
}

function facets(restriction) {
  if (!restriction) return {};
  const enumerations = lista(restriction.enumeration).map((item) => item["@_value"]);
  return {
    base: tipoLocal(restriction["@_base"]),
    enumeration: enumerations.length ? enumerations : null,
    minInclusive: restriction.minInclusive?.["@_value"] ?? null,
    maxInclusive: restriction.maxInclusive?.["@_value"] ?? null,
    minLength: restriction.minLength?.["@_value"] ?? null,
    maxLength: restriction.maxLength?.["@_value"] ?? null,
    pattern: restriction.pattern?.["@_value"] ?? null,
  };
}

function compilarEsquema(xsdTexto) {
  const documento = parserXsd.parse(xsdTexto);
  const schema = documento.schema;
  if (!schema) throw new Error("El XSD no tiene xs:schema");
  const tipos = new Map();
  for (const complejo of lista(schema.complexType)) {
    if (complejo["@_name"]) tipos.set(complejo["@_name"], { kind: "complex", node: complejo });
  }
  for (const simple of lista(schema.simpleType)) {
    if (simple["@_name"]) tipos.set(simple["@_name"], { kind: "simple", node: simple });
  }
  const raices = new Map();
  for (const elemento of lista(schema.element)) {
    raices.set(elemento["@_name"], elemento);
  }
  return { tipos, raices };
}

function definicionHijos(elemento, tipos) {
  if (elemento.complexType) {
    return lista(elemento.complexType.sequence?.element);
  }
  const nombre = tipoLocal(elemento["@_type"]);
  const referido = tipos.get(nombre);
  if (referido?.kind === "complex") {
    return lista(referido.node.sequence?.element);
  }
  return null;
}

function reglasSimples(elemento, tipos) {
  if (elemento.simpleType?.restriction) return facets(elemento.simpleType.restriction);
  const nombre = tipoLocal(elemento["@_type"]);
  const referido = tipos.get(nombre);
  if (referido?.kind === "simple") return facets(referido.node.restriction);
  if (["string", "boolean", "integer", "int", "decimal", "date", "dateTime"].includes(nombre)) {
    return { base: nombre };
  }
  return null;
}

function cumpleSimple(texto, reglas, ruta, errores) {
  const base = reglas.base || "string";
  if (base === "boolean" && texto !== "true" && texto !== "false") {
    errores.push(`${ruta} debe ser boolean`);
    return;
  }
  if ((base === "integer" || base === "int") && !/^-?\d+$/.test(texto)) {
    errores.push(`${ruta} debe ser integer`);
    return;
  }
  if (base === "decimal" && texto !== "" && !/^-?\d+(\.\d+)?$/.test(texto)) {
    errores.push(`${ruta} debe ser decimal`);
    return;
  }
  if (base === "date" && !/^\d{4}-\d{2}-\d{2}$/.test(texto)) {
    errores.push(`${ruta} debe ser date`);
    return;
  }
  if (base === "dateTime" && Number.isNaN(Date.parse(texto))) {
    errores.push(`${ruta} debe ser dateTime`);
    return;
  }
  if (reglas.enumeration && !reglas.enumeration.includes(texto)) {
    errores.push(`${ruta} fuera de la enumeración`);
  }
  if (reglas.pattern && !new RegExp(`^(?:${reglas.pattern})$`).test(texto)) {
    errores.push(`${ruta} no cumple el patrón`);
  }
  if (reglas.minLength != null && texto.length < Number(reglas.minLength)) {
    errores.push(`${ruta} es más corto de lo permitido`);
  }
  if (reglas.maxLength != null && texto.length > Number(reglas.maxLength)) {
    errores.push(`${ruta} es más largo de lo permitido`);
  }
  if (reglas.minInclusive != null && Number(texto) < Number(reglas.minInclusive)) {
    errores.push(`${ruta} es menor que el mínimo`);
  }
  if (reglas.maxInclusive != null && Number(texto) > Number(reglas.maxInclusive)) {
    errores.push(`${ruta} es mayor que el máximo`);
  }
}

function validarElemento(elemento, valor, ruta, tipos, errores) {
  const hijos = definicionHijos(elemento, tipos);
  if (hijos) {
    const opcionales = hijos.every((hijo) => Number(hijo["@_minOccurs"] ?? 1) === 0);
    if (valor === "" || valor == null) {
      if (!opcionales) errores.push(`${ruta} debe ser un elemento complejo`);
      return;
    }
    if (typeof valor !== "object" || Array.isArray(valor)) {
      errores.push(`${ruta} debe ser un elemento complejo`);
      return;
    }
    const esperados = new Set(hijos.map((hijo) => hijo["@_name"]));
    for (const clave of Object.keys(valor)) {
      if (!esperados.has(clave)) errores.push(`${ruta}/${clave} no está en el esquema`);
    }
    for (const hijo of hijos) {
      const nombre = hijo["@_name"];
      const min = Number(hijo["@_minOccurs"] ?? 1);
      const max = hijo["@_maxOccurs"] === "unbounded" ? Infinity : Number(hijo["@_maxOccurs"] ?? 1);
      const presente = valor[nombre];
      if (presente === undefined) {
        if (min > 0) errores.push(`${ruta}/${nombre} es obligatorio`);
        continue;
      }
      const ocurrencias = Array.isArray(presente) ? presente : [presente];
      if (ocurrencias.length < min) errores.push(`${ruta}/${nombre} no alcanza el mínimo`);
      if (ocurrencias.length > max) errores.push(`${ruta}/${nombre} supera el máximo`);
      for (const ocurrencia of ocurrencias) {
        validarElemento(hijo, ocurrencia, `${ruta}/${nombre}`, tipos, errores);
      }
    }
    return;
  }

  const reglas = reglasSimples(elemento, tipos);
  if (!reglas) {
    errores.push(`${ruta} no tiene tipo reconocido`);
    return;
  }
  if (valor != null && typeof valor === "object") {
    errores.push(`${ruta} debe ser un valor simple`);
    return;
  }
  cumpleSimple(valor == null ? "" : String(valor), reglas, ruta, errores);
}

export function validarXmlContraXsd(xmlTexto, xsdTexto) {
  let documento;
  try {
    documento = parserXml.parse(String(xmlTexto || ""));
  } catch {
    return { valido: false, errores: ["XML mal formado"] };
  }
  let esquema;
  try {
    esquema = compilarEsquema(xsdTexto);
  } catch (err) {
    return { valido: false, errores: [err.message] };
  }
  const raices = Object.keys(documento).filter((clave) => !clave.startsWith("?"));
  if (raices.length !== 1) return { valido: false, errores: ["El XML debe tener un solo elemento raíz"] };
  const raiz = raices[0];
  const definicion = esquema.raices.get(raiz);
  if (!definicion) return { valido: false, errores: [`El elemento raíz ${raiz} no está en el XSD`] };
  const errores = [];
  validarElemento(definicion, documento[raiz], raiz, esquema.tipos, errores);
  return { valido: errores.length === 0, errores };
}

export function afirmarXmlValido(xmlTexto, xsdTexto) {
  const resultado = validarXmlContraXsd(xmlTexto, xsdTexto);
  if (!resultado.valido) {
    throw new HttpError(422, "XML_INVALIDO", "El XML no cumple el esquema", {
      errores: resultado.errores,
    });
  }
}

export function leerXsd(directorio, nombre) {
  if (!/^[a-z0-9-]+\.xsd$/.test(nombre)) {
    throw new HttpError(400, "PARAMETRO_INVALIDO", "Nombre de XSD inválido", { campo: "nombre" });
  }
  const archivo = path.resolve(directorio, nombre);
  if (!archivo.startsWith(`${path.resolve(directorio)}${path.sep}`)) {
    throw new HttpError(400, "PARAMETRO_INVALIDO", "Nombre de XSD inválido");
  }
  if (!existsSync(archivo)) throw new HttpError(404, "NO_ENCONTRADO", "El esquema no existe");
  return readFileSync(archivo, "utf8");
}

export function directorioXsd() {
  return path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../xsd");
}

export function listarXsd() {
  return readdirSync(directorioXsd()).filter((nombre) => nombre.endsWith(".xsd"));
}
