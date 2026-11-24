import { randomUUID } from "node:crypto";
import { HttpError, envelopeError, esFalloDeDependencia } from "./errores.js";
import { aXml, parsearXml, quiereXml } from "./xml.js";

export function correlacion(req, res, next) {
  req.correlacionId = req.headers["x-correlation-id"] || randomUUID();
  res.setHeader("X-Correlation-Id", req.correlacionId);
  next();
}

export function leerCuerpoXml(req, _res, next) {
  if (typeof req.body !== "string") return next();
  try {
    req.bodyXml = req.body;
    req.body = parsearXml(req.body);
    req.formatoEntrada = "xml";
    return next();
  } catch (err) {
    return next(err);
  }
}

export function responder(req, res, status, envelope) {
  if (quiereXml(req)) {
    res.status(status);
    res.setHeader("Content-Type", "application/xml; charset=utf-8");
    res.send(aXml(envelope));
    return;
  }
  res.status(status).json(envelope);
}

export function exito(req, res, { status = 200, message, data, pagination, cache, clave }) {
  const envelope = {
    success: true,
    message,
    data,
  };
  if (pagination) envelope.pagination = pagination;
  envelope.meta = {
    cache: cache || "BYPASS",
    servicio: req.app.locals.serviceName,
    correlacion_id: req.correlacionId,
  };
  if (clave) envelope.meta.clave_cache = clave;
  responder(req, res, status, envelope);
}

export function manejadorErrores(log) {
  return (err, req, res, _next) => {
    if (err instanceof SyntaxError && "body" in err) {
      err = new HttpError(400, "JSON_MAL_FORMADO", "El JSON no se pudo leer");
    }
    if (esFalloDeDependencia(err)) {
      log.error("Dependencia no disponible", { error: err.message, path: req.path });
      err = new HttpError(503, "DEPENDENCIA_NO_DISPONIBLE", "Una dependencia no está disponible");
    }
    if (!(err instanceof HttpError)) {
      log.error("Error interno", { error: err.message, path: req.path });
      err = new HttpError(500, "ERROR_TECNICO", "Error interno");
    } else if (err.status >= 500) {
      log.error(err.message, { code: err.code, path: req.path });
    } else {
      log.info("Petición rechazada", { code: err.code, status: err.status, path: req.path });
    }
    responder(req, res, err.status, envelopeError(err));
  };
}

export function noEncontrado(req, res) {
  responder(
    req,
    res,
    404,
    envelopeError(new HttpError(404, "RUTA_NO_ENCONTRADA", "La ruta no existe"))
  );
}
