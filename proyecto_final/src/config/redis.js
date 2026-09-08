import Redis from "ioredis";
import { env } from "./env.js";

export const redis = new Redis(env.redisUrl, {
  maxRetriesPerRequest: 3,
  lazyConnect: true,
});

export async function conectarRedis() {
  if (redis.status === "ready") return redis;
  await redis.connect();
  return redis;
}

export async function verificarRedis() {
  return (await redis.ping()) === "PONG";
}
