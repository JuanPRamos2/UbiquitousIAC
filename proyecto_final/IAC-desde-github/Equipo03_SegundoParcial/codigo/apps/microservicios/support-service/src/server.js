import { app } from "./app.js";

const PUERTO = Number(process.env.PUERTO || 8116);

const servidor = app.listen(PUERTO, "0.0.0.0", () => {
  console.log(`[support-service] Escuchando en puerto ${PUERTO}`);
});

function apagar(senial) {
  console.log(`[support-service] Senial ${senial} recibida: cerrando servidor...`);
  servidor.close(() => {
    console.log("[support-service] Servidor cerrado ordenadamente.");
    process.exit(0);
  });
}

process.on("SIGINT", () => apagar("SIGINT"));
process.on("SIGTERM", () => apagar("SIGTERM"));
