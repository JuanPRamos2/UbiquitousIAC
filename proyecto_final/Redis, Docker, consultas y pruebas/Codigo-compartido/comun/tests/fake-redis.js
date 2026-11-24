export function crearRedisFalso() {
  const datos = new Map();

  function vivo(clave) {
    const item = datos.get(clave);
    if (!item) return null;
    if (item.exp && item.exp <= Date.now()) {
      datos.delete(clave);
      return null;
    }
    return item;
  }

  return {
    async get(clave) {
      return vivo(clave)?.value ?? null;
    },
    async set(clave, valor, ...args) {
      let nx = false;
      let ex = null;
      for (let i = 0; i < args.length; i += 1) {
        if (args[i] === "EX") ex = Number(args[++i]);
        if (args[i] === "NX") nx = true;
      }
      if (nx && vivo(clave)) return null;
      datos.set(clave, { value: String(valor), exp: ex ? Date.now() + ex * 1000 : null });
      return "OK";
    },
    async incr(clave) {
      const previo = vivo(clave);
      const actual = Number(previo?.value || 0) + 1;
      datos.set(clave, { value: String(actual), exp: previo?.exp || null });
      return actual;
    },
    async expire(clave, segundos) {
      const item = vivo(clave);
      if (!item) return 0;
      item.exp = Date.now() + segundos * 1000;
      return 1;
    },
    async ttl(clave) {
      const item = vivo(clave);
      if (!item) return -2;
      if (!item.exp) return -1;
      return Math.max(1, Math.ceil((item.exp - Date.now()) / 1000));
    },
    async del(clave) {
      return datos.delete(clave) ? 1 : 0;
    },
    async exists(clave) {
      return vivo(clave) ? 1 : 0;
    },
    async ping() {
      return "PONG";
    },
    async connect() {},
    async quit() {},
  };
}
