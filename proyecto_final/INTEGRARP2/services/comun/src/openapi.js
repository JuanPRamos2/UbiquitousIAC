import { aXml } from "./xml.js";

const ERRORES = [
  [400, "PARAMETRO_INVALIDO", "Los parámetros no son válidos"],
  [401, "SIN_TOKEN", "Falta el token Bearer"],
  [403, "RBAC", "Perfil sin permiso para este recurso"],
  [404, "NO_ENCONTRADO", "El registro no existe"],
  [409, "CONFLICTO", "La operación entra en conflicto con el estado actual"],
  [422, "XML_INVALIDO", "El cuerpo no cumple el esquema"],
  [429, "LIMITE_EXCEDIDO", "Demasiadas solicitudes"],
  [500, "ERROR_TECNICO", "Error interno"],
  [503, "DEPENDENCIA_NO_DISPONIBLE", "Una dependencia no está disponible"],
];

function errorEjemplo(code, message) {
  return {
    success: false,
    error: { code, message, details: {} },
  };
}

function parametro(definicion) {
  return {
    name: definicion.name,
    in: definicion.in,
    required: Boolean(definicion.required),
    description: definicion.description,
    schema: definicion.schema,
    example: definicion.example,
  };
}

export function construirOpenApi({ titulo, descripcion, version, prefijo, operaciones }) {
  const paths = {};
  const tags = [];
  for (const op of operaciones) {
    const ruta = `${prefijo}${op.ruta}`.replace(/:([A-Za-z0-9_]+)/g, "{$1}");
    paths[ruta] = paths[ruta] || {};
    if (!tags.includes(op.tag)) tags.push(op.tag);
    const parameters = [
      {
        name: "Accept",
        in: "header",
        required: false,
        description: "application/json o application/xml. También se acepta ?format=xml",
        schema: { type: "string" },
        example: "application/json",
      },
      ...(op.parametros || []).map(parametro),
    ];
    const responses = {};
    const ejemplo = op.ejemplo || {
      success: true,
      message: op.resumen,
      data: {},
    };
    responses[op.exito || 200] = {
      description: op.descripcionExito || "Operación correcta",
      content: {
        "application/json": { example: ejemplo },
        "application/xml": { example: aXml(ejemplo) },
      },
    };
    for (const [status, code, message] of ERRORES) {
      if (op.omitirErrores?.includes(status)) continue;
      responses[status] = {
        description: message,
        content: {
          "application/json": { example: errorEjemplo(code, message) },
          "application/xml": { example: aXml(errorEjemplo(code, message)) },
        },
      };
    }
    const operation = {
      tags: [op.tag],
      summary: op.resumen,
      description: `${op.descripcion}\n\nRoles: ${op.roles}.`,
      operationId: op.id,
      security: [{ bearerAuth: [] }],
      parameters,
      responses,
    };
    if (op.cuerpo) {
      operation.requestBody = {
        required: true,
        content: {
          "application/json": { example: op.cuerpo },
          "application/xml": { example: op.cuerpoXml },
        },
      };
    }
    paths[ruta][op.metodo] = operation;
  }

  return {
    openapi: "3.0.3",
    info: { title: titulo, description: descripcion, version },
    servers: [{ url: "/" }],
    tags: tags.map((name) => ({ name })),
    components: {
      securitySchemes: {
        bearerAuth: { type: "http", scheme: "bearer", bearerFormat: "JWT" },
      },
    },
    paths,
  };
}
