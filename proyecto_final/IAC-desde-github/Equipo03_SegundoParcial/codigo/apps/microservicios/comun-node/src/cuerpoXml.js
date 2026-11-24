/**
 * Lectura del cuerpo de la peticion en XML, para los servicios en Node.
 *
 * POR QUE EXISTE
 * --------------
 * Los servicios leian el cuerpo con express.json(). El efecto era que una
 * aplicacion cliente que mandara XML llegaba con req.body vacio y recibia
 * un 422 por "campos obligatorios" aunque los hubiera mandado todos. La
 * aplicacion de escritorio del proyecto consume exclusivamente XML, asi
 * que sin esto no podia hacer ninguna operacion de escritura contra
 * catalog-service ni contra main-process-service.
 *
 * Las reglas son las inversas de xmlizar.js y las MISMAS que
 * comun/xmlizar.py (de_xml), porque un cuerpo XML tiene que significar lo
 * mismo en los dos lenguajes:
 *
 *   - Cada elemento hijo es una clave.
 *   - Una envoltura cuyos hijos se llaman todos igual es una lista.
 *   - xsi:nil="true" produce null, distinto de la cadena vacia.
 *   - NO se adivinan tipos: <valor>4</valor> entrega la cadena "4". Lo
 *     contrario convertiria "007" en 7 y le quitaria informacion a la
 *     validacion de cada servicio, que ya sabe que tipo espera.
 */
import { XMLParser, XMLValidator } from "fast-xml-parser";

import { ErrorApi } from "./errores.js";

const XSI_NIL = "@_xsi:nil";

const lector = new XMLParser({
  ignoreAttributes: false,
  // Sin esto, fast-xml-parser convierte "007" en 7 y "1.0" en 1: adivinar
  // tipos aqui le quita informacion a la validacion de cada servicio.
  parseTagValue: false,
  parseAttributeValue: false,
  trimValues: true,
  // Un elemento vacio tiene que llegar como cadena vacia y no como objeto
  // vacio, para que la validacion de "campo obligatorio" lo detecte.
  isArray: () => false,
});

function quitarEspacio(clave) {
  const i = clave.indexOf(":");
  return i === -1 ? clave : clave.slice(i + 1);
}

function normalizar(valor) {
  if (valor === null || valor === undefined) return "";
  if (typeof valor !== "object") return String(valor);

  // xsi:nil="true" es "no hay dato", distinto de la cadena vacia. La
  // diferencia decide, por ejemplo, si un agregado suprimido se lee como
  // ausente o como cero.
  if (valor[XSI_NIL] === "true" || valor[XSI_NIL] === true) return null;

  const claves = Object.keys(valor).filter((k) => !k.startsWith("@_"));
  if (claves.length === 0) return "";
  if (claves.length === 1 && claves[0] === "#text") return String(valor["#text"]);

  // Una envoltura plural cuyos hijos se llaman todos igual es una lista:
  // <etiquetas><etiqueta/><etiqueta/></etiquetas> produce una lista y no un
  // diccionario con una sola clave repetida. Es la misma regla que
  // comun/xmlizar.py::_de_nodo, y tiene que ser la misma o el mismo cuerpo
  // XML significaria cosas distintas en Python y en Node.
  if (claves.length === 1) {
    const unico = valor[claves[0]];
    if (Array.isArray(unico) && unico.length > 1) return unico.map(normalizar);
  }

  const salida = {};
  for (const clave of claves) {
    if (clave === "#text") continue;
    const limpia = quitarEspacio(clave);
    const v = valor[clave];
    salida[limpia] = Array.isArray(v) ? v.map(normalizar) : normalizar(v);
  }
  return salida;
}

/** Convierte el texto XML de una peticion en un objeto plano. */
export function deXml(texto) {
  // El lector es tolerante por diseno: `<Unidad><nombre>sin cerrar` no le
  // arranca una excepcion, devuelve un arbol a medias. El efecto seria el
  // peor posible: el servicio responderia 422 "campos obligatorios" y el
  // cliente buscaria el error en los datos y no en su XML roto. Por eso se
  // valida la buena formacion ANTES de leer.
  const bienFormado = XMLValidator.validate(texto, { allowBooleanAttributes: true });
  if (bienFormado !== true) {
    const d = bienFormado?.err || {};
    throw new ErrorApi("XML_MAL_FORMADO",
      `El cuerpo no es XML bien formado: ${d.msg || "estructura invalida"}` +
      (d.line ? ` (linea ${d.line})` : ""), 400);
  }

  let crudo;
  try {
    crudo = lector.parse(texto);
  } catch (e) {
    throw new ErrorApi("XML_MAL_FORMADO",
      `El cuerpo no es XML bien formado: ${e.message}`, 400);
  }
  const raices = Object.keys(crudo).filter((k) => !k.startsWith("?"));
  if (raices.length !== 1) {
    throw new ErrorApi("XML_INESPERADO",
      "El cuerpo tiene que traer un solo elemento raiz.", 400);
  }
  const cuerpo = normalizar(crudo[raices[0]]);
  if (cuerpo === null || typeof cuerpo !== "object" || Array.isArray(cuerpo)) {
    throw new ErrorApi("XML_INESPERADO",
      "El elemento raiz del cuerpo tiene que contener los campos como " +
      "elementos hijos.", 400);
  }
  return cuerpo;
}

/**
 * Middleware: deja en req.body el cuerpo XML convertido.
 *
 * Se monta ANTES de express.json() y solo actua cuando el Content-Type es
 * XML, de modo que una peticion en JSON sigue el camino de siempre. El
 * formato se decide por el encabezado y no mirando el primer caracter:
 * adivinar funcionaria casi siempre, y el "casi" de un encabezado mal
 * puesto termina en un error que nadie puede explicar.
 */
export function cuerpoXml(limiteBytes = 262144) {
  return function (req, res, next) {
    const tipo = (req.headers["content-type"] || "").split(";")[0].trim().toLowerCase();
    if (tipo !== "application/xml" && tipo !== "text/xml") return next();

    let texto = "";
    let bytes = 0;
    let excedido = false;
    req.setEncoding("utf8");
    req.on("data", (trozo) => {
      if (excedido) return;
      bytes += Buffer.byteLength(trozo, "utf8");
      if (bytes > limiteBytes) {
        excedido = true;
        next(new ErrorApi("CUERPO_DEMASIADO_GRANDE",
          `El cuerpo pasa de ${limiteBytes} bytes.`, 413));
        return;
      }
      texto += trozo;
    });
    req.on("end", () => {
      if (excedido) return;
      if (!texto.trim()) { req.body = {}; return next(); }
      try {
        req.body = deXml(texto);
        next();
      } catch (e) {
        next(e);
      }
    });
    req.on("error", (e) => next(
      new ErrorApi("CUERPO_ILEGIBLE", `No se pudo leer el cuerpo: ${e.message}`, 400)));
  };
}
