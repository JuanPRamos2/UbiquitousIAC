/**
 * organizational-service — arbol de unidades (8117). No usa MongoDB.
 */
import { montarSwagger } from "@bienestar/comun/openapi.js";
import { ping as pingPostgres } from "@bienestar/comun/postgres.js";
import { ping as pingRedis } from "@bienestar/comun/redis.js";
import { crearServicio } from "@bienestar/comun/servicio.js";

import { router } from "./rutas.js";
import { contratoOpenApi } from "./openapi.js";

export function crearAppOrganizationalService() {
  const { app, montar, finalizar } = crearServicio(
    "organizational-service",
    "Departamentos, jerarquia y plantilla minima.",
    { postgresql: pingPostgres, redis: pingRedis }
  );
  montarSwagger(app, "organizational-service", contratoOpenApi);
  montar("/api/v1", router);
  finalizar();
  return app;
}

export const app = crearAppOrganizationalService();
