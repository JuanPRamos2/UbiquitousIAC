import express from "express";
import cors from "cors";
import helmet from "helmet";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { api } from "./rutas/index.js";
import { correlacion } from "./middlewares/correlacion.js";
import { manejadorErrores } from "./middlewares/error.js";
import { verificarPostgres } from "./config/postgres.js";
import { verificarMongo } from "./config/mongo.js";
import { verificarRedis } from "./config/redis.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const webDir = path.join(__dirname, "../web");

const cspApp = {
  defaultSrc: ["'self'"],
  scriptSrc: ["'self'"],
  styleSrc: ["'self'", "https://fonts.googleapis.com"],
  fontSrc: ["'self'", "https://fonts.gstatic.com", "data:"],
  imgSrc: ["'self'", "data:"],
  connectSrc: ["'self'"],
  objectSrc: ["'none'"],
  baseUri: ["'self'"],
  formAction: ["'self'"],
  frameAncestors: ["'none'"],
};

const cspDocs = {
  ...cspApp,
  scriptSrc: ["'self'", "'unsafe-inline'", "https://cdnjs.cloudflare.com"],
  styleSrc: ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
};

export function crearApp() {
  const app = express();
  app.disable("x-powered-by");
  app.use(
    "/docs",
    helmet({ contentSecurityPolicy: { useDefaults: false, directives: cspDocs } }),
    express.static(path.join(webDir, "docs"))
  );
  app.use(
    helmet({
      contentSecurityPolicy: {
        useDefaults: false,
        directives: cspApp,
      },
    })
  );
  app.use(cors({ origin: false }));
  app.use(express.json({ limit: "32kb" }));
  app.use(correlacion);

  app.get("/api/salud", async (_req, res) => {
    const [postgres, mongo, redisOk] = await Promise.all([
      verificarPostgres().catch(() => false),
      verificarMongo().catch(() => false),
      verificarRedis().catch(() => false),
    ]);
    res.status(postgres && mongo && redisOk ? 200 : 503).json({
      ok: Boolean(postgres && mongo && redisOk),
      postgres,
      mongo,
      redis: redisOk,
    });
  });

  app.use("/api", api);
  app.use(express.static(webDir));
  app.use(manejadorErrores);
  return app;
}
