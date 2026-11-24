import Redis from "ioredis";
import { config } from "./env.js";
import { setRedisCliente } from "../utilidades/cache.js";

export const redis = new Redis(config.redisUrl, {
  maxRetriesPerRequest: 3,
  lazyConnect: true,
});

setRedisCliente(redis);

export async function conectarRedis() {
  if (redis.status === "ready") return redis;
  try {
    await redis.connect();
    setRedisCliente(redis);
  } catch (err) {
    console.warn("No se pudo conectar a Redis para catalog-service:", err.message);
  }
  return redis;
}

export async function verificarRedis() {
  try {
    return (await redis.ping()) === "PONG";
  } catch {
    return false;
  }
}
