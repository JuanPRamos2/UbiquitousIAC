/**
 * support-service — solicitudes de apoyo (8116).
 */
import { montarSwagger } from "@bienestar/comun/openapi.js";
import { ping as pingMongo } from "@bienestar/comun/mongo.js";
import { ping as pingPostgres } from "@bienestar/comun/postgres.js";
import { ping as pingRedis } from "@bienestar/comun/redis.js";
import { crearServicio } from "@bienestar/comun/servicio.js";

import { router } from "./rutas.js";
import { contratoOpenApi } from "./openapi.js";

export function crearAppSupportService() {
  const { app, montar, finalizar } = crearServicio(
    "support-service",
    "Solicitudes de apoyo confidenciales, ligadas al seudonimo.",
    { postgresql: pingPostgres, redis: pingRedis, mongodb: pingMongo }
  );
  montarSwagger(app, "support-service", contratoOpenApi);
  montar("/api/v1", router);
  finalizar();
  return app;
}

export const app = crearAppSupportService();
