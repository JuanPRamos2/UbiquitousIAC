/** Redis: sesiones, lista de revocados, cache de catalogos y limite de consumo. */
import Redis from "ioredis";
import { redis as cfg } from "./entorno.js";

let cliente = null;

export function obtenerRedis() {
  if (cliente === null) {
    cliente = new Redis({
      host: cfg.host, port: cfg.port,
      connectTimeout: 2000,
      // Una sola reintento por orden: si Redis no esta, la peticion debe
      // fallar en menos de lo que tarda en responder la sonda del
      // llamador, no quedarse colgada reintentando.
      maxRetriesPerRequest: 1,
      // La cola de espera SI queda activa: la conexion de ioredis se
      // establece de forma asincrona y, sin cola, la primera orden del
      // arranque falla con "Stream isn't writeable" aunque Redis este
      // perfectamente levantado.
      enableOfflineQueue: true,
      lazyConnect: false,
      retryStrategy: (intentos) => (intentos > 10 ? null : Math.min(intentos * 200, 2000)),
    });
    cliente.on("error", () => { /* se reporta en /health/ready, no en la consola */ });
  }
  return cliente;
}

export async function ping() {
  const r = await obtenerRedis().ping();
  if (r !== "PONG") throw new Error("Redis no respondio PONG");
  return true;
}

export async function verificarRedis() {
  try { await ping(); return true; } catch { return false; }
}

export async function cerrarRedis() {
  if (cliente) { cliente.disconnect(); cliente = null; }
}
