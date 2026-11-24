const PROHIBIDOS = new Set([
  "password",
  "contrasena",
  "contraseña",
  "authorization",
  "token",
  "jwt",
  "secret",
  "jwt_secret",
  "postgres_password",
]);

function limpiar(valor, profundidad = 0) {
  if (profundidad > 4 || valor == null) return valor;
  if (Array.isArray(valor)) return valor.map((item) => limpiar(item, profundidad + 1));
  if (typeof valor !== "object") return valor;
  const salida = {};
  for (const [clave, item] of Object.entries(valor)) {
    if (PROHIBIDOS.has(clave.toLowerCase())) {
      salida[clave] = "[omitido]";
      continue;
    }
    salida[clave] = limpiar(item, profundidad + 1);
  }
  return salida;
}

export function crearLogger(servicio) {
  function escribir(nivel, msg, extra = {}) {
    const linea = JSON.stringify({
      time: new Date().toISOString(),
      level: nivel,
      service: servicio,
      msg,
      ...limpiar(extra),
    });
    if (nivel === "error") console.error(linea);
    else console.log(linea);
  }

  return {
    info(msg, extra) {
      escribir("info", msg, extra);
    },
    warn(msg, extra) {
      escribir("warn", msg, extra);
    },
    error(msg, extra) {
      escribir("error", msg, extra);
    },
  };
}

export const loggerSilencioso = {
  info() {},
  warn() {},
  error() {},
};
