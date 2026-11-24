import fs from "node:fs";
import path from "node:path";

function cargarEnvLocal() {
  const rutaEnv = path.resolve(process.cwd(), ".env");
  if (!fs.existsSync(rutaEnv)) return;
  const texto = fs.readFileSync(rutaEnv, "utf8");
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

export const config = {
  nodeEnv: process.env.NODE_ENV || "development",
  port: Number(process.env.CATALOG_SERVICE_PORT || process.env.PORT || 3002),
  jwtSecret: process.env.JWT_SECRET || "dev-only-change-me",
  postgres: {
    host: process.env.POSTGRES_HOST || "localhost",
    port: Number(process.env.POSTGRES_PORT || 5433),
    database: process.env.POSTGRES_DB || "bienestar_nexum",
    user: process.env.POSTGRES_USER || "postgres",
    password: process.env.POSTGRES_PASSWORD || "postgres",
    max: 10,
  },
  redisUrl: process.env.REDIS_URL || "redis://localhost:6379",
  cacheTtlSec: Number(process.env.CATALOG_CACHE_TTL_SEC || 300),
};
