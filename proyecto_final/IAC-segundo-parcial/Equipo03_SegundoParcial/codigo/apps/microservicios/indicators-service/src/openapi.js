import { crearContratoOpenApi } from "@bienestar/comun/openapi.js";

export const contratoOpenApi = crearContratoOpenApi({
  nombre: "indicators-service",
  version: "1.0.0",
  descripcion: "Servicio de calculo y agregacion de indicadores organizacionales de estres, carga y bienestar con garantia k >= 5 (Puerto 8113).",
  rutas: {
    "/api/v1/indicadores": {
      get: {
        summary: "Lista el catalogo de metricas e indicadores de bienestar autorizados",
        security: [{ bearerAuth: [] }],
        responses: {
          200: { description: "Catalogo de indicadores" },
          401: { $ref: "#/components/responses/NoAutenticado" },
          403: { $ref: "#/components/responses/SinPermiso" },
        },
      },
    },
    "/api/v1/indicadores/agregados": {
      get: {
        summary: "Consulta indicadores agregados por campania y unidad con umbral k >= 5",
        security: [{ bearerAuth: [] }],
        parameters: [
          { name: "campania_id", in: "query", required: true, schema: { type: "string" } },
          { name: "unidad_id", in: "query", required: true, schema: { type: "string" } },
        ],
        responses: {
          200: { description: "Indicadores agregados protegidos" },
          400: { $ref: "#/components/responses/SolicitudInvalida" },
          403: { $ref: "#/components/responses/SinPermiso" },
        },
      },
    },
    "/api/v1/indicadores/historico": {
      get: {
        summary: "Consulta evolucion temporal e historico de indicadores para una unidad",
        security: [{ bearerAuth: [] }],
        parameters: [
          { name: "unidad_id", in: "query", required: true, schema: { type: "string" } },
          { name: "dimension_id", in: "query", schema: { type: "string" } },
        ],
        responses: {
          200: { description: "Serie historica de indicadores" },
          400: { $ref: "#/components/responses/SolicitudInvalida" },
        },
      },
    },
    "/api/v1/indicadores/calcular": {
      post: {
        summary: "Dispara procesamiento y consolidacion de indicadores agregados",
        security: [{ bearerAuth: [] }],
        responses: {
          200: { description: "Calculo completado" },
          401: { $ref: "#/components/responses/NoAutenticado" },
          403: { $ref: "#/components/responses/SinPermiso" },
        },
      },
    },
  },
  esquemas: {
    Indicador: {
      type: "object",
      properties: {
        clave: { type: "string" },
        nombre: { type: "string" },
        dimension: { type: "string" },
        unidad_medida: { type: "string" },
        umbral_alerta: { type: "number" },
      },
    },
    AgregadoIndicador: {
      type: "object",
      properties: {
        clave: { type: "string" },
        nombre: { type: "string" },
        valor: { type: "number", nullable: true },
        muestra_n: { type: "integer" },
        suprimido_por_umbral: { type: "boolean" },
        nivel_riesgo: { type: "string" },
      },
    },
  },
});
