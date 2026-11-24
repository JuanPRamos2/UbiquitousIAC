import { HttpError } from "../../../comun/src/errores.js";
import { paginar } from "../../../comun/src/paginacion.js";
import { alcanceUnidad } from "../../../comun/src/perfiles.js";

async function conCache(cache, contador, recurso, partes, calcular) {
  const resultado = await cache.obtener(recurso, partes, calcular);
  await contador.incrementar();
  return resultado;
}

function empaquetar(resultado, page, limit) {
  return {
    filas: resultado.valor.filas,
    pagination: resultado.valor.pagination || paginar(page, limit, resultado.valor.total),
    cache: resultado.cache,
    clave: resultado.clave,
  };
}

export function crearServicioConsultas({ repo, cache, contador }) {
  return {
    async campanias(actor, filtros) {
      const resultado = await conCache(cache, contador, "campanias", { filtros, perfil: actor.perfil }, () =>
        repo.campanias(filtros)
      );
      return empaquetar(resultado, filtros.page, filtros.limit);
    },
    async campania(actor, id) {
      const resultado = await conCache(cache, contador, "campania", { id, perfil: actor.perfil }, async () => {
        const fila = await repo.campaniaPorId(id);
        if (!fila) throw new HttpError(404, "NO_ENCONTRADO", "La campaña no existe");
        return { fila };
      });
      return { fila: resultado.valor.fila, cache: resultado.cache, clave: resultado.clave };
    },
    async unidades(actor, filtros) {
      const resultado = await conCache(cache, contador, "unidades", { filtros, perfil: actor.perfil }, () =>
        repo.unidades(filtros)
      );
      return empaquetar(resultado, filtros.page, filtros.limit);
    },
    async unidad(actor, id) {
      const resultado = await conCache(cache, contador, "unidad", { id, perfil: actor.perfil }, async () => {
        const fila = await repo.unidadPorId(id);
        if (!fila) throw new HttpError(404, "NO_ENCONTRADO", "La unidad no existe");
        return { fila };
      });
      return { fila: resultado.valor.fila, cache: resultado.cache, clave: resultado.clave };
    },
    async instrumentos(actor, filtros) {
      const resultado = await conCache(cache, contador, "instrumentos", { filtros, perfil: actor.perfil }, () =>
        repo.instrumentos(filtros)
      );
      return empaquetar(resultado, filtros.page, filtros.limit);
    },
    async fuentes(actor, filtros) {
      const resultado = await conCache(cache, contador, "fuentes", { filtros, perfil: actor.perfil }, () =>
        repo.fuentes(filtros)
      );
      return empaquetar(resultado, filtros.page, filtros.limit);
    },
    async intervenciones(actor, filtros) {
      const unidad = alcanceUnidad(actor, filtros.unidad_organizacional_id, HttpError);
      const efectivos = { ...filtros, unidad_organizacional_id: unidad };
      const resultado = await conCache(
        cache,
        contador,
        "intervenciones",
        { filtros: efectivos, usuario: actor.usuario_id, perfil: actor.perfil },
        () => repo.intervenciones(efectivos)
      );
      return empaquetar(resultado, filtros.page, filtros.limit);
    },
    async intervencion(actor, id) {
      const resultado = await conCache(
        cache,
        contador,
        "intervencion",
        { id, usuario: actor.usuario_id, perfil: actor.perfil },
        async () => {
          const fila = await repo.intervencionPorId(id);
          if (!fila) throw new HttpError(404, "NO_ENCONTRADO", "La intervención no existe");
          if (
            actor.perfil === "LIDER" &&
            fila.unidad_organizacional_id !== actor.unidad_organizacional_id
          ) {
            throw new HttpError(403, "RBAC", "Solo puedes consultar intervenciones de tu unidad");
          }
          return { fila };
        }
      );
      return { fila: resultado.valor.fila, cache: resultado.cache, clave: resultado.clave };
    },
    async auditoria(actor, filtros) {
      const resultado = await conCache(
        cache,
        contador,
        "auditoria",
        { filtros, usuario: actor.usuario_id, perfil: actor.perfil },
        () => repo.auditoria(filtros)
      );
      return empaquetar(resultado, filtros.page, filtros.limit);
    },
    async resultados(actor, filtros) {
      const unidad = alcanceUnidad(actor, filtros.unidad_organizacional_id, HttpError);
      const efectivos = { ...filtros, unidad_organizacional_id: unidad };
      const resultado = await conCache(
        cache,
        contador,
        "resultados",
        { filtros: efectivos, usuario: actor.usuario_id, perfil: actor.perfil },
        () => repo.resultados(efectivos)
      );
      return empaquetar(resultado, filtros.page, filtros.limit);
    },
    async presupuesto(actor, filtros) {
      const unidad = alcanceUnidad(actor, filtros.unidad_organizacional_id, HttpError);
      const efectivos = { ...filtros, unidad_organizacional_id: unidad };
      const resultado = await conCache(
        cache,
        contador,
        "presupuesto",
        { filtros: efectivos, usuario: actor.usuario_id, perfil: actor.perfil },
        () => repo.presupuesto(efectivos)
      );
      return empaquetar(resultado, filtros.page, filtros.limit);
    },
    async solicitudes(actor, filtros) {
      const resultado = await conCache(
        cache,
        contador,
        "solicitudes",
        { filtros, usuario: actor.usuario_id, perfil: actor.perfil },
        () => repo.solicitudes(filtros)
      );
      return empaquetar(resultado, filtros.page, filtros.limit);
    },
    async participacion(actor) {
      const resultado = await conCache(
        cache,
        contador,
        "participacion",
        { usuario: actor.usuario_id },
        async () => {
          const fila = await repo.participacion(actor.usuario_id);
          if (!fila) throw new HttpError(404, "NO_ENCONTRADO", "No hay participación asociada a su usuario");
          return { fila };
        }
      );
      return { fila: resultado.valor.fila, cache: resultado.cache, clave: resultado.clave };
    },
    async observabilidad() {
      const consultas = await contador.leer();
      return consultas;
    },
  };
}
