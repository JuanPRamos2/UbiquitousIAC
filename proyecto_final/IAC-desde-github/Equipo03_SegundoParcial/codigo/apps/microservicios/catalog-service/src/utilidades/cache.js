/** Cache de catalogos en Redis. Los nombres locales envuelven a comun/cache.js. */
import { claveDe, guardar, invalidar, leer } from "@bienestar/comun/cache.js";

export const construirClaveCache = claveDe;
export const leerCache = leer;
export const guardarCache = guardar;
export const invalidarCacheRecurso = invalidar;
