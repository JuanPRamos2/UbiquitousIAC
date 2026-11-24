/**
 * catalog-service — CRUD de catalogos sobre PostgreSQL (Integrante 2).
 *
 * Responsabilidad unica: administrar unidades organizacionales,
 * instrumentos, versiones, reactivos y campanias. No calcula agregados, no
 * emite tokens y no toca MongoDB.
 *
 * La fabrica comun aporta correlacion, bitacora, las tres sondas de salud,
 * el sobre de error unico y la respuesta dual JSON/XML, de modo que este
 * archivo solo declara lo propio del servicio.
 */
import { montarSwagger } from "@bienestar/comun/openapi.js";
import { ping as pingPostgres } from "@bienestar/comun/postgres.js";
import { ping as pingRedis } from "@bienestar/comun/redis.js";
import { crearServicio } from "@bienestar/comun/servicio.js";

import { catalogoV1Router } from "./rutas/catalogo.rutas.js";

export function crearAppCatalogService() {
  const { app, montar, finalizar } = crearServicio(
    "catalog-service",
    "Catalogos de unidades, instrumentos, reactivos y campanias.",
    {
      // PostgreSQL es indispensable: sin el, el servicio no puede atender.
      postgresql: pingPostgres,
      // Redis solo acelera. Se reporta en la sonda para que quien opera
      // sepa que la cache esta caida, pero el servicio sigue respondiendo.
      redis: pingRedis,
    }
  );

  montarSwagger(app, "catalog-service", new URL("../openapi.yaml", import.meta.url));
  montar("/api/v1/catalogos", catalogoV1Router);
  finalizar();
  return app;
}

export const app = crearAppCatalogService();
