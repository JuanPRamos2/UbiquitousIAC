import fs from "node:fs";
import path from "node:path";

function cargarEnvLocal() {
  const archivo = path.resolve(process.cwd(), ".env");
  if (!fs.existsSync(archivo)) return;
  const texto = fs.readFileSync(archivo, "utf8");
  for (const linea of texto.split("\n")) {
    const recorte = linea.trim();
    if (!recorte || recorte.startsWith("#")) continue;
    const eq = recorte.indexOf("=");
    if (eq < 1) continue;
    const clave = recorte.slice(0, eq).trim();
    let valor = recorte.slice(eq + 1).trim();
    if (
      (valor.startsWith('"') && valor.endsWith('"')) ||
      (valor.startsWith("'") && valor.endsWith("'"))
    ) {
      valor = valor.slice(1, -1);
    }
    if (process.env[clave] === undefined) process.env[clave] = valor;
  }
}

cargarEnvLocal();

export const env = {
  nodeEnv: process.env.NODE_ENV || "development",
  port: Number(process.env.PORT || 3000),
  jwtSecret: process.env.JWT_SECRET || "dev-only-change-me",
  jwtExpiresSec: Number(process.env.JWT_EXPIRES_SEC || 900),
  loginMaxIntentos: Number(process.env.LOGIN_MAX_INTENTOS || 5),
  redisTtl: {
    cacheAgregadoSec: Number(process.env.REDIS_TTL_CACHE_AGREGADO_SEC || 300),
    lockAgregadoSec: Number(process.env.REDIS_TTL_LOCK_AGREGADO_SEC || 10),
  },
  postgres: {
    host: process.env.POSTGRES_HOST || "localhost",
    port: Number(process.env.POSTGRES_PORT || 5432),
    database: process.env.POSTGRES_DB || "bienestar_nexum",
    user: process.env.POSTGRES_USER || "postgres",
    password: process.env.POSTGRES_PASSWORD || "postgres",
    max: 10,
  },
  mongoUrl: process.env.MONGO_URL || "mongodb://localhost:27017",
  mongoDb: process.env.MONGO_DB || "bienestar_nexum",
  redisUrl: process.env.REDIS_URL || "redis://localhost:6379",
};

if (env.jwtSecret === "dev-only-change-me" || env.jwtSecret === "cambia-esta-clave-en-produccion") {
  console.warn("JWT_SECRET usa el valor de desarrollo. Cámbialo antes de una demostración real.");
}
