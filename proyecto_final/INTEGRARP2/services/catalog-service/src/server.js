import { crearAppCatalogService } from "./app.js";

const puerto = Number(process.env.CATALOG_SERVICE_PORT || process.env.PORT || 3002);
const app = crearAppCatalogService();

app.listen(puerto, () => {
  console.log(`[catalog-service] Activo y escuchando en http://0.0.0.0:${puerto}`);
  console.log(`[catalog-service] Sonda de salud en http://0.0.0.0:${puerto}/health`);
  console.log(`[catalog-service] Catálogos v1 en http://0.0.0.0:${puerto}/api/v1/catalogos`);
});
