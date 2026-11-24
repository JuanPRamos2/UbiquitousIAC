import { app } from "./app.js";

const PUERTO = Number(process.env.PUERTO || 8117);

const servidor = app.listen(PUERTO, "0.0.0.0", () => {
  console.log(`[organizational-service] Escuchando en puerto ${PUERTO}`);
});

function apagar(senial) {
  console.log(`[organizational-service] Senial ${senial} recibida: cerrando servidor...`);
  servidor.close(() => {
    console.log("[organizational-service] Servidor cerrado ordenadamente.");
    process.exit(0);
  });
}

process.on("SIGINT", () => apagar("SIGINT"));
process.on("SIGTERM", () => apagar("SIGTERM"));
