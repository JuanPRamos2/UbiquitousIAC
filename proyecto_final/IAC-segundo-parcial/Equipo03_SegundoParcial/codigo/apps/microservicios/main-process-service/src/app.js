/**
 * main-process-service — proceso principal del negocio (Integrante 2).
 *
 * Responsabilidad unica: registrar una respuesta de campania y llevar el
 * ciclo de vida de las solicitudes de apoyo. Escribe en PostgreSQL por
 * medio de la funcion del motor y en MongoDB el documento de la entrega y
 * los eventos del proceso.
 *
 * La sonda /health/ready reporta las tres dependencias por separado para
 * que quien opera sepa cual falta: con PostgreSQL caido el servicio no
 * puede aceptar una respuesta; con MongoDB caido si puede, y la respuesta
 * queda registrada con el documento marcado como pendiente, porque una
 * persona no va a volver a contestar la encuesta.
 */
import { montarSwagger } from "@bienestar/comun/openapi.js";
import { ping as pingMongo } from "@bienestar/comun/mongo.js";
import { ping as pingPostgres } from "@bienestar/comun/postgres.js";
import { ping as pingRedis } from "@bienestar/comun/redis.js";
import { crearServicio } from "@bienestar/comun/servicio.js";

import { procesoV1Router } from "./rutas/proceso.rutas.js";

export function crearAppMainProcessService() {
  const { app, montar, finalizar } = crearServicio(
    "main-process-service",
    "Proceso principal: respuestas de campania y solicitudes de apoyo.",
    { postgresql: pingPostgres, mongodb: pingMongo, redis: pingRedis }
  );

  montarSwagger(app, "main-process-service", new URL("../openapi.yaml", import.meta.url));
  montar("/api/v1", procesoV1Router);
  finalizar();
  return app;
}

export const app = crearAppMainProcessService();
