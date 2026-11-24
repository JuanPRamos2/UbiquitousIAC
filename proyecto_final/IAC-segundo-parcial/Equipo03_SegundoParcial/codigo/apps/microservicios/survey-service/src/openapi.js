import { crearContratoOpenApi } from "@bienestar/comun/openapi.js";

export const contratoOpenApi = crearContratoOpenApi({
  nombre: "survey-service",
  version: "1.0.0",
  descripcion: "Servicio de administracion de cuestionarios, escalas, borradores y captura de respuestas de bienestar (Puerto 8112).",
  rutas: {
    "/api/v1/cuestionarios": {
      get: {
        summary: "Lista cuestionarios de evaluacion activos o disponibles",
        security: [{ bearerAuth: [] }],
        parameters: [
          { name: "activo", in: "query", schema: { type: "boolean" } },
        ],
        responses: {
          200: { description: "Listado de cuestionarios" },
          401: { $ref: "#/components/responses/NoAutenticado" },
          403: { $ref: "#/components/responses/SinPermiso" },
        },
      },
      post: {
        summary: "Crea o actualiza definicion de cuestionario",
        security: [{ bearerAuth: [] }],
        responses: {
          201: { description: "Cuestionario creado" },
          400: { $ref: "#/components/responses/SolicitudInvalida" },
          401: { $ref: "#/components/responses/NoAutenticado" },
          403: { $ref: "#/components/responses/SinPermiso" },
        },
      },
    },
    "/api/v1/cuestionarios/{id}": {
      get: {
        summary: "Obtiene detalle completo de un cuestionario con sus preguntas y escalas",
        security: [{ bearerAuth: [] }],
        parameters: [
          { name: "id", in: "path", required: true, schema: { type: "string" } },
        ],
        responses: {
          200: { description: "Detalle del cuestionario" },
          404: { $ref: "#/components/responses/NoEncontrado" },
        },
      },
    },
    "/api/v1/cuestionarios/{id}/borrador": {
      get: {
        summary: "Recupera el borrador temporal de respuestas del colaborador",
        security: [{ bearerAuth: [] }],
        parameters: [
          { name: "id", in: "path", required: true, schema: { type: "string" } },
        ],
        responses: {
          200: { description: "Borrador de encuesta" },
          404: { $ref: "#/components/responses/NoEncontrado" },
        },
      },
      put: {
        summary: "Guarda o actualiza borrador temporal de respuestas (con expiracion TTL)",
        security: [{ bearerAuth: [] }],
        parameters: [
          { name: "id", in: "path", required: true, schema: { type: "string" } },
        ],
        responses: {
          200: { description: "Borrador guardado exitosamente" },
          400: { $ref: "#/components/responses/SolicitudInvalida" },
        },
      },
    },
    "/api/v1/cuestionarios/{id}/respuestas": {
      post: {
        summary: "Registra respuestas definitivas de la encuesta (valida completitud y evita duplicados)",
        security: [{ bearerAuth: [] }],
        parameters: [
          { name: "id", in: "path", required: true, schema: { type: "string" } },
        ],
        responses: {
          201: { description: "Respuestas registradas exitosamente" },
          400: { $ref: "#/components/responses/SolicitudInvalida" },
          409: { description: "Encuesta ya respondida previamente para esta campania" },
        },
      },
    },
  },
  esquemas: {
    Cuestionario: {
      type: "object",
      properties: {
        cuestionario_id: { type: "string" },
        nombre: { type: "string" },
        tipo: { type: "string" },
        descripcion: { type: "string" },
        escala_min: { type: "integer" },
        escala_max: { type: "integer" },
        activo: { type: "boolean" },
      },
    },
    Borrador: {
      type: "object",
      properties: {
        cuestionario_id: { type: "string" },
        seudonimo_id: { type: "string" },
        respuestas: { type: "array", items: { type: "object" } },
        fecha_actualizacion: { type: "string", format: "date-time" },
      },
    },
  },
});
