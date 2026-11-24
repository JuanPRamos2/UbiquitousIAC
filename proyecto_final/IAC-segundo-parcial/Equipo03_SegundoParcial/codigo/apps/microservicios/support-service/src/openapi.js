import { crearContratoOpenApi } from "@bienestar/comun/openapi.js";

export const contratoOpenApi = crearContratoOpenApi({
  nombre: "support-service",
  version: "1.0.0",
  descripcion: "Servicio de gestion confidencial de solicitudes de apoyo emocional asignadas exclusivamente a especialistas (Puerto 8116).",
  rutas: {
    "/api/v1/apoyo/solicitudes": {
      post: {
        summary: "Crea una solicitud voluntaria de apoyo confidencial mediante seudonimo",
        security: [{ bearerAuth: [] }],
        responses: {
          201: { description: "Solicitud de apoyo creada exitosamente" },
          400: { $ref: "#/components/responses/SolicitudInvalida" },
          401: { $ref: "#/components/responses/NoAutenticado" },
          403: { $ref: "#/components/responses/SinPermiso" },
        },
      },
      get: {
        summary: "Lista solicitudes de apoyo para atencion por parte de especialistas autorizados",
        security: [{ bearerAuth: [] }],
        parameters: [
          { name: "estado", in: "query", schema: { type: "string", enum: ["ABIERTA", "EN_PROCESO", "CERRADA"] } },
          { name: "pagina", in: "query", schema: { type: "integer" } },
          { name: "tamano", in: "query", schema: { type: "integer" } },
        ],
        responses: {
          200: { description: "Listado de solicitudes de apoyo" },
          401: { $ref: "#/components/responses/NoAutenticado" },
          403: { $ref: "#/components/responses/SinPermiso" },
        },
      },
    },
    "/api/v1/apoyo/solicitudes/{id}": {
      get: {
        summary: "Consulta el detalle y bitacora de atencion de una solicitud",
        security: [{ bearerAuth: [] }],
        parameters: [
          { name: "id", in: "path", required: true, schema: { type: "string" } },
        ],
        responses: {
          200: { description: "Detalle de la solicitud de apoyo" },
          404: { $ref: "#/components/responses/NoEncontrado" },
        },
      },
    },
    "/api/v1/apoyo/solicitudes/{id}/estado": {
      put: {
        summary: "Actualiza el estado de atencion de la solicitud con notas confidenciales",
        security: [{ bearerAuth: [] }],
        parameters: [
          { name: "id", in: "path", required: true, schema: { type: "string" } },
        ],
        responses: {
          200: { description: "Estado actualizado" },
          400: { $ref: "#/components/responses/SolicitudInvalida" },
          409: { description: "Transicion de estado no permitida" },
        },
      },
    },
    "/api/v1/apoyo/solicitudes/{id}/mensajes": {
      post: {
        summary: "Registra comunicacion o nota protegida entre especialista y solicitante",
        security: [{ bearerAuth: [] }],
        parameters: [
          { name: "id", in: "path", required: true, schema: { type: "string" } },
        ],
        responses: {
          201: { description: "Mensaje agregado" },
          400: { $ref: "#/components/responses/SolicitudInvalida" },
        },
      },
    },
  },
  esquemas: {
    SolicitudApoyo: {
      type: "object",
      properties: {
        id: { type: "string" },
        seudonimo_id: { type: "string" },
        mensaje: { type: "string" },
        fecha: { type: "string", format: "date-time" },
        estado: { type: "string", enum: ["ABIERTA", "EN_PROCESO", "CERRADA"] },
        fecha_actualizacion: { type: "string", format: "date-time", nullable: true },
        historial: { type: "array", items: { type: "object" } },
      },
    },
  },
});
