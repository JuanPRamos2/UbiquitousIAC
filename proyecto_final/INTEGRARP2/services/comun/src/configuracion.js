let avisoSecreto = false;

export function origenPermitido(origin, lista) {
  if (!origin) return true;
  if (lista.includes(origin)) return true;
  return /^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/.test(origin);
}

export function configuracion() {
  const jwtSecret = process.env.JWT_SECRET || process.env.JWT_SECRETO || "dev-only-change-me";
  if (!avisoSecreto && (jwtSecret === "dev-only-change-me" || jwtSecret === "cambia-esta-clave-en-produccion")) {
    avisoSecreto = true;
    console.warn(
      JSON.stringify({
        level: "warn",
        service: process.env.SERVICE_NAME || "nexum",
        msg: "JWT_SECRET usa el valor de desarrollo. Cámbialo antes de una demostración real.",
      })
    );
  }

  return {
    serviceName: process.env.SERVICE_NAME || "nexum",
    port: Number(process.env.PORT || 3000),
    jwtSecret,
    jwtPublicKey: process.env.JWT_PUBLIC_KEY || "",
    jwtAlgorithm: process.env.JWT_ALGORITHM || "HS256",
    jwtIssuer: process.env.JWT_ISSUER || "",
    jwtAudience: process.env.JWT_AUDIENCE || "",
    requireSession: (process.env.JWT_REQUIRE_SESSION || "true") !== "false",
    cacheTtl: Number(process.env.CACHE_TTL_SEC || 60),
    lockTtl: Number(process.env.REDIS_TTL_LOCK_SEC || 10),
    contextoTtl: Number(process.env.REDIS_TTL_CONTEXTO_SEC || 60),
    rateLimit: Number(process.env.RATE_LIMIT_REQUESTS || 60),
    rateWindow: Number(process.env.RATE_LIMIT_WINDOW_SEC || 60),
    postgres: {
      host: process.env.POSTGRES_HOST || "127.0.0.1",
      port: Number(process.env.POSTGRES_PORT || 5433),
      database: process.env.POSTGRES_DB || "bienestar_nexum",
      user: process.env.POSTGRES_USER || "postgres",
      password: process.env.POSTGRES_PASSWORD || "postgres",
      max: 10,
      connectionTimeoutMillis: 3000,
    },
    mongoUrl: process.env.MONGO_URL || "mongodb://127.0.0.1:27017",
    mongoDb: process.env.MONGO_DB || "bienestar_nexum",
    redisUrl: process.env.REDIS_URL || "redis://127.0.0.1:6379",
    corsOrigins: (process.env.CORS_ORIGINS || "http://127.0.0.1:3000,http://localhost:3000")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  };
}
