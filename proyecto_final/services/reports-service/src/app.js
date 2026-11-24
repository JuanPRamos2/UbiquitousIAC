import express from "express";
import cors from "cors";
import helmet from "helmet";
import swaggerUi from "swagger-ui-express";
import { crearCache, crearContador } from "../../comun/src/cache.js";
import { configuracion, origenPermitido } from "../../comun/src/configuracion.js";
import { crearConexiones } from "../../comun/src/conexiones.js";
import { HttpError } from "../../comun/src/errores.js";
import { correlacion, exito, leerCuerpoXml, manejadorErrores, noEncontrado } from "../../comun/src/http.js";
import { crearAutenticacion } from "../../comun/src/jwt.js";
import { crearLogger } from "../../comun/src/logger.js";
import { construirOpenApi } from "../../comun/src/openapi.js";
import { crearAutorizar } from "../../comun/src/perfiles.js";
import { crearRateLimit } from "../../comun/src/rate-limit.js";
import { directorioXsd, leerXsd, listarXsd } from "../../comun/src/xsd.js";
import { crearRepositorio } from "./repositorios/reportes.repositorio.js";
import { operaciones, reportesRouter } from "./rutas/reportes.rutas.js";
import { crearServicioReportes } from "./servicios/reportes.servicio.js";

export function crearApp(opciones = {}) {
  const cfg = { ...configuracion(), serviceName: "reports-service", ...opciones };
  const log = opciones.log || crearLogger(cfg.serviceName);
  const conexiones = opciones.conexiones || crearConexiones(cfg, log);
  const cache = crearCache({ redis: conexiones.redis, cfg, log });
  const contador = crearContador({ redis: conexiones.redis, log, operacion: "reports:generados" });
  const repo = opciones.repo || crearRepositorio({
    query: (texto, params) => conexiones.pool.query(texto, params),
    mongo: conexiones.mongo,
  });
  const servicio = opciones.servicio || crearServicioReportes({ repo, cache, contador });
  const autenticar = crearAutenticacion({
    redis: conexiones.redis,
    query: (texto, params) => conexiones.pool.query(texto, params),
    cfg,
    log,
  });
  const autorizar = crearAutorizar(HttpError);
  const limitar = crearRateLimit({ redis: conexiones.redis, cfg, log });

  const app = express();
  app.disable("x-powered-by");
  app.locals.serviceName = cfg.serviceName;
  app.locals.servicio = servicio;
  app.use(helmet({ contentSecurityPolicy: false, crossOriginResourcePolicy: { policy: "cross-origin" } }));
  app.use(cors({
    origin(origin, callback) {
      if (origenPermitido(origin, cfg.corsOrigins)) return callback(null, true);
      return callback(null, false);
    },
    allowedHeaders: ["Authorization", "Content-Type", "Accept", "X-Correlation-Id"],
    exposedHeaders: ["X-RateLimit-Limit", "X-RateLimit-Remaining", "Retry-After", "X-Correlation-Id"],
  }));
  app.use(express.json({ limit: "32kb" }));
  app.use(express.text({ type: ["application/xml", "text/xml", "application/*+xml"], limit: "32kb" }));
  app.use(correlacion);
  app.use(leerCuerpoXml);

  app.get("/health", async (_req, res) => {
    const salud = await conexiones.estado();
    res.status(salud.status === "healthy" ? 200 : 503).json({ ...salud, service: cfg.serviceName });
  });

  const spec = construirOpenApi({
    titulo: "Nexum Reports Service",
    descripcion:
      "Reportes agregados de Bienestar Nexum en forma de categorías y series para Highcharts. " +
      "Los datos salen de PostgreSQL y MongoDB. No recalcula privacidad diferencial ni expone respuestas individuales.",
    version: "1.0.0",
    prefijo: "/api/v1/reports",
    operaciones,
  });
  app.get("/api/docs.json", (_req, res) => res.json(spec));
  app.use("/api/docs", swaggerUi.serve, swaggerUi.setup(spec, { swaggerOptions: { persistAuthorization: true } }));
  app.get("/api/v1/xsd", (req, res) => {
    exito(req, res, { message: "Esquemas XSD", data: { esquemas: listarXsd() }, cache: "BYPASS" });
  });
  app.get("/api/v1/xsd/:nombre", (req, res, next) => {
    try {
      const nombre = req.params.nombre.endsWith(".xsd") ? req.params.nombre : `${req.params.nombre}.xsd`;
      res.status(200).setHeader("Content-Type", "application/xml; charset=utf-8").send(leerXsd(directorioXsd(), nombre));
    } catch (err) {
      next(err);
    }
  });

  const api = express.Router();
  api.use(autenticar);
  api.use(limitar);
  api.use("/reports", reportesRouter(autorizar));
  app.use("/api/v1", api);
  app.use(noEncontrado);
  app.use(manejadorErrores(log));
  return { app, conexiones, cfg, log, servicio };
}
