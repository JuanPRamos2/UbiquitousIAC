import { crearAppMainProcessService } from "./app.js";

const puerto = Number(process.env.PUERTO || process.env.PORT || 8000);
const app = crearAppMainProcessService();

app.listen(puerto, "0.0.0.0", () => {
  console.log(`[main-process-service] escuchando en http://0.0.0.0:${puerto}`);
  console.log(`[main-process-service] salud   http://0.0.0.0:${puerto}/health/ready`);
  console.log(`[main-process-service] swagger http://0.0.0.0:${puerto}/docs`);
});
