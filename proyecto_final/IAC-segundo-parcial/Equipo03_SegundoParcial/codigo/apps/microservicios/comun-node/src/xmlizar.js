/**
 * Serializacion a XML, con las MISMAS reglas que comun/xmlizar.py.
 *
 * Que las reglas sean una sola importa porque los XSD de contratos/xml
 * describen las dos implementaciones a la vez. Si el serializador de Node
 * envolviera las listas de otra forma, el mismo esquema no podria validar
 * la respuesta de catalog-service y la de users-service.
 *
 * Reglas:
 *   - Cada clave del objeto es un elemento.
 *   - Una lista se envuelve en un elemento plural con hijos en singular:
 *     { unidades: [...] } produce <unidades><unidad/>...</unidades>.
 *     Sin esa envoltura un esquema no puede distinguir una lista de un
 *     elemento repetido.
 *   - null se escribe con xsi:nil="true", no como cadena vacia: la
 *     diferencia entre "no hay dato" y "el dato es vacio" importa, por
 *     ejemplo en un agregado suprimido por el umbral.
 *   - Los booleanos se escriben en su forma canonica de XML Schema.
 */

export const ESPACIO = "http://nexum.com.mx/bienestar/v1";
export const XSI = "http://www.w3.org/2001/XMLSchema-instance";

const SINGULARES = {
  usuarios: "usuario", perfiles: "perfil", permisos: "permiso",
  documentos: "documento", notificaciones: "notificacion",
  detalles: "detalle", elementos: "elemento", evidencias: "evidencia",
  campanias: "campania", unidades: "unidad", destinatarios: "destinatario",
  instrumentos: "instrumento", reactivos: "reactivo", versiones: "version",
  solicitudes: "solicitud", respuestas: "respuesta", eventos: "evento",
  historial: "entrada", agregados: "agregado", dimensiones: "dimension",
  valores: "valor", reportes: "reporte", consultas: "consulta",
  series: "serie", puntos: "punto", intervenciones: "intervencion",
  indices: "indice", archivos: "archivo", servicios: "servicio",
  // "fuentes" caia en la regla de -es y se partia en "fuent". Las
  // excepciones se declaran en lugar de afinar la regla: una regla
  // morfologica mas lista fallaria en otra palabra y seria mas dificil de
  // depurar que una tabla que se lee de un golpe.
  fuentes: "fuente", filas: "fila", celdas: "celda", columnas: "columna",
  formatos: "formato", entradas: "entrada",
  // Los compuestos tambien: la regla le quita la "s" a la ultima palabra y
  // deja "intervenciones_sugerida", que no es singular de nada y no cumple
  // el XSD. Esta tabla tiene que ser IGUAL a la de comun/xmlizar.py; hay
  // una prueba que las compara.
  intervenciones_sugeridas: "intervencion_sugerida",
  reglas: "regla", detecciones: "deteccion", corridas: "corrida",
  no_evaluables: "no_evaluable", advertencias: "advertencia",
  acciones: "accion", lecturas: "lectura", supresiones: "supresion",
  cuestionarios: "cuestionario", borradores: "borrador", indicadores: "indicador",
  comunicaciones: "comunicacion", especialistas: "especialista", nodos: "nodo",
  diagnosticos: "diagnostico", simulaciones: "simulacion", padrones: "padron",
  parametros: "parametro", opciones: "opcion", metadatos: "metadato",
};

function singular(plural) {
  const p = String(plural);
  if (SINGULARES[p]) return SINGULARES[p];
  if (p.endsWith("es") && p.length > 3) return p.slice(0, -2);
  if (p.endsWith("s") && p.length > 2) return p.slice(0, -1);
  return "elemento";
}

function escapar(s) {
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&apos;");
}

function texto(v) {
  if (typeof v === "boolean") return v ? "true" : "false";
  if (v instanceof Date) return v.toISOString();
  return String(v);
}

function nombreValido(k) {
  const n = String(k).replace(/[^\w.-]/g, "_");
  return /^[A-Za-z_]/.test(n) ? n : `_${n}`;
}

function poblar(clave, valor, sangria) {
  const tag = nombreValido(clave);
  const pre = "  ".repeat(sangria);

  if (valor === null || valor === undefined) {
    return `${pre}<${tag} xsi:nil="true"/>`;
  }
  if (Array.isArray(valor)) {
    const hijo = singular(clave);
    if (valor.length === 0) return `${pre}<${tag}/>`;
    const dentro = valor.map((item) => poblar(hijo, item, sangria + 1)).join("\n");
    return `${pre}<${tag}>\n${dentro}\n${pre}</${tag}>`;
  }
  if (typeof valor === "object" && !(valor instanceof Date)) {
    const claves = Object.keys(valor);
    if (claves.length === 0) return `${pre}<${tag}/>`;
    const dentro = claves.map((k) => poblar(k, valor[k], sangria + 1)).join("\n");
    return `${pre}<${tag}>\n${dentro}\n${pre}</${tag}>`;
  }
  return `${pre}<${tag}>${escapar(texto(valor))}</${tag}>`;
}

export function aXml(datos, raiz = "respuesta") {
  const tag = nombreValido(raiz);
  const cuerpo = Object.keys(datos || {})
    .map((k) => poblar(k, datos[k], 1))
    .join("\n");
  const abre =
    `<${tag} xmlns="${ESPACIO}" xmlns:xsi="${XSI}" ` +
    `xsi:schemaLocation="${ESPACIO} ${tag}.xsd">`;
  return `<?xml version="1.0" encoding="UTF-8"?>\n${abre}\n${cuerpo}\n</${tag}>`;
}
