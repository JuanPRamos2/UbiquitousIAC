import { crearApp } from "./app.js";

const { app, conexiones, cfg, log } = crearApp();

async function main() {
  await conexiones.conectar();
  app.listen(cfg.port, "0.0.0.0", () => {
    log.info("Servicio iniciado", { puerto: cfg.port, servicio: cfg.serviceName });
  });
}

async function shutdown() {
  log.info("Servicio deteniéndose");
  await conexiones.cerrar();
  process.exit(0);
}

process.on("unhandledRejection", (err) => {
  log.error("Promesa no controlada", { error: err?.message || String(err) });
});

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);

main().catch((err) => {
  log.error("No se pudo iniciar el servicio", { error: err.message });
  process.exit(1);
});
