export class HttpError extends Error {
  constructor(status, code, message, details) {
    super(message);
    this.name = "HttpError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function asyncHandler(fn) {
  return (req, res, next) => {
    Promise.resolve(fn(req, res, next)).catch(next);
  };
}

export function envelopeError(err) {
  return {
    success: false,
    error: {
      code: err.code || "ERROR_TECNICO",
      message: err.message || "Error interno",
      details: err.details && typeof err.details === "object" ? err.details : {},
    },
  };
}

export function esFalloDeDependencia(err) {
  const codigo = err?.code;
  const nombre = err?.name || "";
  return (
    codigo === "ECONNREFUSED" ||
    codigo === "ENOTFOUND" ||
    codigo === "ETIMEDOUT" ||
    codigo === "57P01" ||
    codigo === "ECONNRESET" ||
    nombre.includes("Mongo") ||
    /connect|EAI_AGAIN|Connection is closed/i.test(err?.message || "")
  );
}
