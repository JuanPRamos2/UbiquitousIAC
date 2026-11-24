import Redis from "ioredis";
import pg from "pg";
import { MongoClient } from "mongodb";

export function crearConexiones(cfg, log) {
  const redis = new Redis(cfg.redisUrl, {
    lazyConnect: true,
    maxRetriesPerRequest: 1,
    enableOfflineQueue: false,
    connectTimeout: 3000,
  });
  redis.on("error", (err) => {
    log.warn("Redis reportó un error", { error: err.message });
  });

  const pool = new pg.Pool(cfg.postgres);
  pool.on("error", (err) => {
    log.error("PostgreSQL reportó un error de pool", { error: err.message });
  });

  let mongoClient;
  let mongoBase;

  async function mongo() {
    if (mongoBase) return mongoBase;
    mongoClient = new MongoClient(cfg.mongoUrl, {
      serverSelectionTimeoutMS: 3000,
      maxPoolSize: 8,
    });
    await mongoClient.connect();
    mongoBase = mongoClient.db(cfg.mongoDb);
    await mongoBase.collection("solicitudes_apoyo").createIndex({ fecha: -1 });
    return mongoBase;
  }

  return {
    redis,
    pool,
    mongo,
    async conectar() {
      const tareas = [
        redis.connect().catch((err) => {
          log.error("Redis no conectó al arranque", { error: err.message });
        }),
        pool.query("SELECT 1").catch((err) => {
          log.error("PostgreSQL no conectó al arranque", { error: err.message });
        }),
        mongo().catch((err) => {
          log.error("MongoDB no conectó al arranque", { error: err.message });
        }),
      ];
      await Promise.all(tareas);
    },
    async cerrar() {
      await redis.quit().catch(() => {});
      await pool.end().catch(() => {});
      if (mongoClient) await mongoClient.close().catch(() => {});
    },
    async estado() {
      const dependencias = { postgres: "down", mongo: "down", redis: "down" };
      await Promise.all([
        pool
          .query("SELECT 1 AS ok")
          .then(() => {
            dependencias.postgres = "up";
          })
          .catch(() => {}),
        mongo()
          .then((db) => db.command({ ping: 1 }))
          .then(() => {
            dependencias.mongo = "up";
          })
          .catch(() => {}),
        redis
          .ping()
          .then((valor) => {
            if (valor === "PONG") dependencias.redis = "up";
          })
          .catch(() => {}),
      ]);
      const sano = Object.values(dependencias).every((item) => item === "up");
      return {
        status: sano ? "healthy" : "unhealthy",
        dependencies: dependencias,
      };
    },
  };
}
