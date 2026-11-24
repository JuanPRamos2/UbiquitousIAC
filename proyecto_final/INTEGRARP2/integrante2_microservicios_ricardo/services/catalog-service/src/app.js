import express from "express";
import cors from "cors";
import helmet from "helmet";
import { catalogoV1Router } from "./rutas/catalogo.rutas.js";
import { verificarPostgres } from "./config/postgres.js";
import { verificarRedis } from "./config/redis.js";
import { responderCatalogo } from "./utilidades/serializador.js";

export function crearAppCatalogService() {
  const app = express();
  app.disable("x-powered-by");

  app.use(helmet());
  app.use(cors());
  app.use(express.json({ limit: "64kb" }));

  // Endpoint obligatorio /health
  app.get("/health", async (req, res) => {
    const [pgOk, redisOk] = await Promise.all([
      verificarPostgres().catch(() => false),
      verificarRedis().catch(() => false),
    ]);

    const status = pgOk ? "UP" : "DOWN";
    const payload = {
      status,
      service: "catalog-service",
      version: "1.0.0",
      timestamp: new Date().toISOString(),
      dependencies: {
        postgresql: Boolean(pgOk),
        redis: Boolean(redisOk),
      },
    };

    responderCatalogo(req, res, payload, {
      rootTag: "salud",
      status: pgOk ? 200 : 503,
    });
  });

  // Rutas versionadas del microservicio
  app.use("/api/v1/catalogos", catalogoV1Router);

  // Manejo de errores estandarizado (alineado con contratos/xml/comun.xsd y Error.schema.json)
  app.use((err, req, res, _next) => {
    const statusCode = err.status || err.statusCode || 500;
    const errorBody = {
      error: {
        codigo: err.code || err.codigo || (statusCode === 500 ? "ERROR_INTERNO" : "ERROR"),
        mensaje: err.message || "Error interno del servidor",
      },
    };
    responderCatalogo(req, res, errorBody, { rootTag: "error_respuesta", status: statusCode });
  });

  return app;
}
