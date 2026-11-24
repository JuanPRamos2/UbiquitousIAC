import { crearContratoOpenApi } from "@bienestar/comun/openapi.js";

export const contratoOpenApi = crearContratoOpenApi({
  nombre: "organizational-service",
  version: "1.0.0",
  descripcion: "Servicio de administracion de jerarquias organizacionales y control de plantilla minima k >= 5 para prevencion de inferencia (Puerto 8117).",
  rutas: {
    "/api/v1/organizacion/unidades": {
      get: {
        summary: "Lista unidades organizacionales disponibles o activas",
        security: [{ bearerAuth: [] }],
        responses: {
          200: { description: "Listado de unidades" },
          401: { $ref: "#/components/responses/NoAutenticado" },
          403: { $ref: "#/components/responses/SinPermiso" },
        },
      },
      post: {
        summary: "Crea una nueva unidad organizacional (exige plantilla declarada >= 5)",
        security: [{ bearerAuth: [] }],
        responses: {
          201: { description: "Unidad creada exitosamente" },
          400: { $ref: "#/components/responses/SolicitudInvalida" },
          403: { $ref: "#/components/responses/SinPermiso" },
          409: { $ref: "#/components/responses/ValidacionFallida" },
        },
      },
    },
    "/api/v1/organizacion/unidades/{id}": {
      get: {
        summary: "Obtiene detalle de una unidad organizacional",
        security: [{ bearerAuth: [] }],
        parameters: [
          { name: "id", in: "path", required: true, schema: { type: "string" } },
        ],
        responses: {
          200: { description: "Detalle de la unidad" },
          404: { $ref: "#/components/responses/NoEncontrado" },
        },
      },
      put: {
        summary: "Actualiza los atributos de una unidad organizacional",
        security: [{ bearerAuth: [] }],
        parameters: [
          { name: "id", in: "path", required: true, schema: { type: "string" } },
        ],
        responses: {
          200: { description: "Unidad actualizada" },
          400: { $ref: "#/components/responses/SolicitudInvalida" },
        },
      },
      delete: {
        summary: "Baja logica de la unidad (valida que no tenga dependencias hijas activas)",
        security: [{ bearerAuth: [] }],
        parameters: [
          { name: "id", in: "path", required: true, schema: { type: "string" } },
        ],
        responses: {
          200: { description: "Unidad desactivada" },
          409: { description: "Tiene dependencias hijas activas" },
        },
      },
    },
    "/api/v1/organizacion/unidades/{id}/arbol": {
      get: {
        summary: "Recupera la jerarquia y arbol subordinado completo usando CTE recursivo",
        security: [{ bearerAuth: [] }],
        parameters: [
          { name: "id", in: "path", required: true, schema: { type: "string" } },
        ],
        responses: {
          200: { description: "Arbol jerarquico de unidades subordinadas" },
          404: { $ref: "#/components/responses/NoEncontrado" },
        },
      },
    },
  },
  esquemas: {
    UnidadOrganizacional: {
      type: "object",
      properties: {
        unidad_id: { type: "string" },
        nombre: { type: "string" },
        descripcion: { type: "string" },
        tipo: { type: "string" },
        padre_id: { type: "string", nullable: true },
        nivel: { type: "integer" },
        plantilla_declarada: { type: "integer" },
        activa: { type: "boolean" },
      },
    },
  },
});
