import * as Bitacora from "../modelos/Bitacora.js";

export async function registrarAsync(evento) {
  setImmediate(() => {
    Bitacora.registrarBitacora(evento).catch((err) => {
      console.error("bitacora_auditoria", err.message);
    });
  });
}
