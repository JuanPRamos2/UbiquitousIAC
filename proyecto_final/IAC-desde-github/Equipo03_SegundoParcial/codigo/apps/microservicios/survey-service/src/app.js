/**
 * survey-service — cuestionarios (8112). Misma fabrica que catalog y proceso.
 */
import { montarSwagger } from "@bienestar/comun/openapi.js";
import { ping as pingMongo } from "@bienestar/comun/mongo.js";
import { ping as pingPostgres } from "@bienestar/comun/postgres.js";
import { ping as pingRedis } from "@bienestar/comun/redis.js";
import { crearServicio } from "@bienestar/comun/servicio.js";

import { router } from "./rutas.js";
import { contratoOpenApi } from "./openapi.js";

export function crearAppSurveyService() {
  const { app, montar, finalizar } = crearServicio(
    "survey-service",
    "Cuestionarios, borradores y una sola respuesta por campania.",
    { postgresql: pingPostgres, redis: pingRedis, mongodb: pingMongo }
  );
  montarSwagger(app, "survey-service", contratoOpenApi);
  montar("/api/v1", router);
  finalizar();
  return app;
}

export const app = crearAppSurveyService();
