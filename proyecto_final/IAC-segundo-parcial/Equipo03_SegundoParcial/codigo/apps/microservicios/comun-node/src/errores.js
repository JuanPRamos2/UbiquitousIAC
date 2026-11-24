/**
 * Manejo estandarizado de errores, identico al de los microservicios en
 * Python (apps/microservicios/comun/comun/errores.py).
 *
 * Forma unica del error, en JSON o en XML:
 *
 *   { "error": { "codigo", "mensaje", "detalles": [], "correlacion_id" } }
 *
 * El codigo es estable y sirve para programar contra el; el mensaje puede
 * cambiar de redaccion sin romper a ningun cliente. Que los ocho servicios
 * devuelvan el mismo sobre es lo que permite a la aplicacion movil y a la
 * de escritorio escribir su manejo de errores una sola vez.
 */
import { mostrarErrores } from "./entorno.js";
import { aXml } from "./xmlizar.js";

export class ErrorApi extends Error {
  constructor(codigo, mensaje, http = 400, detalles = []) {
    super(mensaje);
    this.name = "ErrorApi";
    this.codigo = codigo;
    this.mensaje = mensaje;
    this.http = http;
    this.detalles = detalles || [];
  }
}

/**
 * Alias con el orden de argumentos que usa el codigo del Integrante 2:
 * new HttpError(404, "NO_ENCONTRADO", "mensaje"). Hereda de ErrorApi para
 * que el manejador central lo reconozca y devuelva el mismo sobre que el
 * resto de los servicios, en JSON o en XML.
 */
export class HttpError extends ErrorApi {
  constructor(http, codigo, mensaje, extra = {}) {
    const detalles = Array.isArray(extra) ? extra
      : (extra && Object.keys(extra).length ? [extra] : []);
    super(codigo || "ERROR", mensaje, http, detalles);
    this.name = "HttpError";
    this.status = http;
    this.code = codigo;
    this.extra = Array.isArray(extra) ? {} : (extra || {});
  }
}

/** El formato se decide por Accept, o por ?formato=xml para probar en el navegador. */
export function quiereXml(req) {
  if (!req) return false;
  const q = String(req.query?.formato || req.query?.format || "").toLowerCase();
  if (q === "xml") return true;
  const accept = String(req.headers?.accept || "").toLowerCase();
  return accept.includes("xml") && !accept.includes("json");
}

export function cuerpoError(req, codigo, mensaje, detalles = []) {
  return {
    error: {
      codigo,
      mensaje,
      detalles: detalles || [],
      correlacion_id: req?.correlacionId || "",
    },
  };
}

export function responderError(req, res, codigo, mensaje, http, detalles = []) {
  const cuerpo = cuerpoError(req, codigo, mensaje, detalles);
  if (quiereXml(req)) {
    res.status(http).type("application/xml; charset=utf-8");
    return res.send(aXml(cuerpo, "error_respuesta"));
  }
  return res.status(http).json(cuerpo);
}

/** Se registra DESPUES de las rutas: Express elige el manejador por aridad. */
export function registrarManejadores(app, bitacora) {
  app.use((req, res) => {
    responderError(req, res, "RECURSO_NO_ENCONTRADO",
      "La ruta solicitada no existe en este servicio.", 404);
  });

  app.use((err, req, res, _next) => {
    if (err instanceof ErrorApi) {
      return responderError(req, res, err.codigo, err.mensaje, err.http, err.detalles);
    }
    if (err?.type === "entity.parse.failed") {
      return responderError(req, res, "CUERPO_INVALIDO",
        "El cuerpo de la peticion no es JSON valido.", 400);
    }
    if (err?.type === "entity.too.large") {
      return responderError(req, res, "CUERPO_DEMASIADO_GRANDE",
        "El cuerpo de la peticion excede el limite permitido.", 413);
    }
    // Una caida del almacen NO es un error interno del servicio: el
    // servicio funciona y su dependencia no. La diferencia es util de
    // verdad -- 503 le dice al cliente que reintente mas tarde y a quien
    // opera donde mirar; 500 le dice que el codigo esta roto y manda a
    // revisar el lugar equivocado. Los nombres de error del driver de
    // MongoDB se reconocen por su clase, no por el texto del mensaje, que
    // cambia entre versiones.
    const nombre = String(err?.name || "");
    const mensajeCrudo = String(err?.message || "");
    const esAlmacen =
      nombre.startsWith("Mongo") ||
      nombre === "MongoServerSelectionError" ||
      /Topology is closed|ENOTFOUND|ECONNREFUSED/.test(mensajeCrudo);
    if (esAlmacen) {
      bitacora?.error("El almacen de datos no responde", mensajeCrudo);
      return responderError(req, res, "ALMACEN_NO_DISPONIBLE",
        "El almacen de documentos (MongoDB) no responde, asi que esta " +
        "operacion no se puede completar ahora. El servicio esta arriba: " +
        "lo que falta es su dependencia. Reintenta en unos momentos.",
        503, [{ campo: "mongodb", problema: mensajeCrudo.slice(0, 160) }]);
    }

    bitacora?.error("Error no controlado", err?.stack || err);
    // Fuera de developer no se devuelve el detalle: el rastro de una
    // excepcion puede revelar la estructura interna del sistema.
    const detalle = mostrarErrores
      ? String(err?.message || err)
      : "Error interno del servicio. El evento quedo registrado.";
    return responderError(req, res, "ERROR_INTERNO", detalle, 500);
  });
}
