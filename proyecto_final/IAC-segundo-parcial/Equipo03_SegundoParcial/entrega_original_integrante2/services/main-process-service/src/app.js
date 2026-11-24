import express from "express";
import cors from "cors";
import helmet from "helmet";
import { procesoV1Router } from "./rutas/proceso.rutas.js";
import { verificarMongo } from "../../../src/config/mongo.js";
import { verificarPostgres } from "../../../src/config/postgres.js";
import { responderProceso, manejadorErroresProceso } from "./utilidades/serializador.js";
import { correlacion } from "../../../src/middlewares/correlacion.js";

export function crearAppMainProcessService() {
  const app = express();
  app.disable("x-powered-by");

  app.use(helmet());
  app.use(cors());
  app.use(express.json({ limit: "64kb" }));
  app.use(correlacion);

  // Sonda de salud obligatoria
  app.get("/health", async (req, res) => {
    const [mongoOk, pgOk] = await Promise.all([
      verificarMongo().catch(() => false),
      verificarPostgres().catch(() => false),
    ]);

    const status = mongoOk ? "UP" : "DOWN";
    const payload = {
      status,
      service: "main-process-service",
      version: "1.0.0",
      timestamp: new Date().toISOString(),
      dependencies: {
        mongodb: Boolean(mongoOk),
        postgresql: Boolean(pgOk),
      },
    };

    responderProceso(req, res, payload, {
      rootTag: "salud",
      status: mongoOk ? 200 : 503,
    });
  });

  // Rutas versionadas del microservicio
  app.use("/api/v1", procesoV1Router);

  // Manejador centralizado de errores con soporte dual JSON/XML
  app.use(manejadorErroresProceso);

  return app;
}
