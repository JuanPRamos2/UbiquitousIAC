import { crearAppMainProcessService } from "./app.js";

const puerto = Number(process.env.MAIN_PROCESS_SERVICE_PORT || process.env.PORT || 3003);
const app = crearAppMainProcessService();

app.listen(puerto, () => {
  console.log(`[main-process-service] Activo y escuchando en http://0.0.0.0:${puerto}`);
  console.log(`[main-process-service] Sonda de salud en http://0.0.0.0:${puerto}/health`);
  console.log(`[main-process-service] Proceso principal v1 en http://0.0.0.0:${puerto}/api/v1/encuestas`);
});
