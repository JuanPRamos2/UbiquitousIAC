import { crearApp } from "./app.js";
import { env } from "./config/env.js";
import { conectarMongo, cerrarMongo } from "./config/mongo.js";
import { conectarRedis, redis } from "./config/redis.js";
import { pgPool } from "./config/postgres.js";

const app = crearApp();

async function main() {
  await conectarMongo();
  await conectarRedis();
  app.listen(env.port, "0.0.0.0", () => {
    console.log(`Bienestar Nexum en http://127.0.0.1:${env.port}`);
  });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

async function shutdown() {
  await cerrarMongo().catch(() => {});
  await redis.quit().catch(() => {});
  await pgPool.end().catch(() => {});
  process.exit(0);
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
