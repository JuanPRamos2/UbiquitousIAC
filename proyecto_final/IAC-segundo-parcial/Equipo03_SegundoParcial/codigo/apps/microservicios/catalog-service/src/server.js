import { crearAppCatalogService } from "./app.js";

const puerto = Number(process.env.PUERTO || process.env.PORT || 8000);
const app = crearAppCatalogService();

app.listen(puerto, "0.0.0.0", () => {
  console.log(`[catalog-service] escuchando en http://0.0.0.0:${puerto}`);
  console.log(`[catalog-service] salud      http://0.0.0.0:${puerto}/health/ready`);
  console.log(`[catalog-service] swagger    http://0.0.0.0:${puerto}/docs`);
  console.log(`[catalog-service] catalogos  http://0.0.0.0:${puerto}/api/v1/catalogos`);
});
