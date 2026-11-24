import express from "express";
import cors from "cors";
import helmet from "helmet";
import swaggerUi from "swagger-ui-express";
import { crearCache, crearContador } from "../../comun/src/cache.js";
import { configuracion, origenPermitido } from "../../comun/src/configuracion.js";
import { crearConexiones } from "../../comun/src/conexiones.js";
import { HttpError } from "../../comun/src/errores.js";
import {
  correlacion,
  exito,
  leerCuerpoXml,
  manejadorErrores,
  noEncontrado,
} from "../../comun/src/http.js";
import { crearAutenticacion } from "../../comun/src/jwt.js";
import { crearLogger } from "../../comun/src/logger.js";
import { construirOpenApi } from "../../comun/src/openapi.js";
import { crearAutorizar } from "../../comun/src/perfiles.js";
import { crearRateLimit } from "../../comun/src/rate-limit.js";
import { directorioXsd, leerXsd, listarXsd } from "../../comun/src/xsd.js";
import { crearRepositorio } from "./repositorios/consultas.repositorio.js";
import { consultasRouter, operaciones } from "./rutas/consultas.rutas.js";
import { crearServicioConsultas } from "./servicios/consultas.servicio.js";

export function crearApp(opciones = {}) {
  const cfg = { ...configuracion(), serviceName: "queries-service", ...opciones };
  const log = opciones.log || crearLogger(cfg.serviceName);
  const conexiones = opciones.conexiones || crearConexiones(cfg, log);
  const cache = crearCache({ redis: conexiones.redis, cfg, log });
  const contador = crearContador({ redis: conexiones.redis, log, operacion: "queries:consultas" });
  const repo = opciones.repo || crearRepositorio({ query: (texto, params) => conexiones.pool.query(texto, params), mongo: conexiones.mongo });
  const servicio = opciones.servicio || crearServicioConsultas({ repo, cache, contador });
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
  app.locals.HttpError = HttpError;
  app.use(helmet({ contentSecurityPolicy: false, crossOriginResourcePolicy: { policy: "cross-origin" } }));
  app.use(
    cors({
      origin(origin, callback) {
        if (origenPermitido(origin, cfg.corsOrigins)) return callback(null, true);
        return callback(null, false);
      },
      allowedHeaders: ["Authorization", "Content-Type", "Accept", "X-Correlation-Id"],
      exposedHeaders: ["X-RateLimit-Limit", "X-RateLimit-Remaining", "Retry-After", "X-Correlation-Id"],
    })
  );
  app.use(express.json({ limit: "32kb" }));
  app.use(express.text({ type: ["application/xml", "text/xml", "application/*+xml"], limit: "32kb" }));
  app.use(correlacion);
  app.use(leerCuerpoXml);
  app.use((req, res, next) => {
    const inicio = Date.now();
    res.on("finish", () => {
      log.info("Petición atendida", {
        method: req.method,
        path: req.path,
        status: res.statusCode,
        ms: Date.now() - inicio,
        usuario_id: req.actor?.usuario_id,
      });
    });
    next();
  });

  app.get("/health", async (_req, res) => {
    const salud = await conexiones.estado();
    const status = salud.status === "healthy" ? 200 : 503;
    res.status(status).json({ ...salud, service: cfg.serviceName });
  });

  const spec = construirOpenApi({
    titulo: "Nexum Queries Service",
    descripcion:
      "Consultas de solo lectura del dominio de bienestar laboral. No expone respuestas individuales. " +
      "Acepte application/json o application/xml. La autenticación JWT es la del Auth Service del equipo.",
    version: "1.0.0",
    prefijo: "/api/v1/queries",
    operaciones,
  });
  app.get("/api/docs.json", (_req, res) => res.json(spec));
  app.use("/api/docs", swaggerUi.serve, swaggerUi.setup(spec, { swaggerOptions: { persistAuthorization: true } }));

  app.get("/api/v1/xsd", (req, res) => {
    exito(req, res, {
      message: "Esquemas XSD de queries-service y reports-service",
      data: { esquemas: listarXsd() },
      cache: "BYPASS",
    });
  });
  app.get("/api/v1/xsd/:nombre", (req, res, next) => {
    try {
      const nombre = req.params.nombre.endsWith(".xsd") ? req.params.nombre : `${req.params.nombre}.xsd`;
      const texto = leerXsd(directorioXsd(), nombre);
      res.status(200);
      res.setHeader("Content-Type", "application/xml; charset=utf-8");
      res.send(texto);
    } catch (err) {
      next(err);
    }
  });

  const api = express.Router();
  api.use(autenticar);
  api.use(limitar);
  api.use("/queries", consultasRouter(autorizar));
  app.use("/api/v1", api);
  app.use(noEncontrado);
  app.use(manejadorErrores(log));

  return { app, conexiones, cfg, log, servicio };
}
